from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.constants import MANDATORY_MUST_TYPES
from app.core.exceptions import AppError
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.document_version import DocumentVersion
from app.models.requirement import Requirement
from app.models.requirement_prerequisite import RequirementPrerequisite
from app.schemas.requirement import RequirementCreate, RequirementUpdate


def _validate_source_refs(
    db: Session,
    document_id: Optional[int],
    version_id: Optional[int],
    chunk_id: Optional[int],
) -> None:
    if document_id is not None:
        if not db.query(Document).filter(Document.id == document_id).first():
            raise AppError("source_document_id not found", 404, "source_document_not_found")
    if version_id is not None:
        v = db.query(DocumentVersion).filter(DocumentVersion.id == version_id).first()
        if not v:
            raise AppError("source_version_id not found", 404, "source_version_not_found")
        if document_id is not None and v.document_id != document_id:
            raise AppError(
                "source_version does not belong to source_document",
                400,
                "source_version_mismatch",
            )
    if chunk_id is not None:
        c = db.query(DocumentChunk).filter(DocumentChunk.id == chunk_id).first()
        if not c:
            raise AppError("source_chunk_id not found", 404, "source_chunk_not_found")
        if document_id is not None and c.document_id != document_id:
            raise AppError(
                "source_chunk does not belong to source_document",
                400,
                "source_chunk_mismatch",
            )


def is_mandatory_derived(must_type: str) -> bool:
    return must_type in MANDATORY_MUST_TYPES


def create_requirement(db: Session, data: RequirementCreate, actor_id: Optional[int]) -> Requirement:
    if db.query(Requirement).filter(Requirement.req_code == data.req_code).first():
        raise AppError("Requirement code already exists", 409, "req_code_taken")

    _validate_source_refs(
        db, data.source_document_id, data.source_version_id, data.source_chunk_id
    )

    req = Requirement(
        req_code=data.req_code.strip(),
        title=data.title.strip(),
        description=data.description,
        requirement_type=data.requirement_type,
        must_type=data.must_type,
        priority=data.priority,
        due_stage=data.due_stage,
        competency=data.competency,
        assessment_topic=data.assessment_topic,
        source_document_id=data.source_document_id,
        source_version_id=data.source_version_id,
        source_chunk_id=data.source_chunk_id,
        source_section=data.source_section,
        created_by=actor_id,
    )
    db.add(req)
    db.flush()
    return req


def list_requirements(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
    requirement_type: Optional[str] = None,
    must_type: Optional[str] = None,
    source_document_id: Optional[int] = None,
    include_inactive: bool = False,
) -> Tuple[List[Requirement], int]:
    q = db.query(Requirement)
    if not include_inactive:
        q = q.filter(Requirement.is_active.is_(True))
    if requirement_type:
        q = q.filter(Requirement.requirement_type == requirement_type)
    if must_type:
        q = q.filter(Requirement.must_type == must_type)
    if source_document_id:
        q = q.filter(Requirement.source_document_id == source_document_id)
    if search:
        like = f"%{search.strip()}%"
        q = q.filter(
            (Requirement.title.ilike(like))
            | (Requirement.req_code.ilike(like))
            | (Requirement.competency.ilike(like))
            | (Requirement.description.ilike(like))
        )
    total = q.count()
    items = q.order_by(Requirement.req_code.asc()).offset(skip).limit(limit).all()
    return items, total


def get_requirement(db: Session, req_id: int) -> Requirement:
    req = db.query(Requirement).filter(Requirement.id == req_id).first()
    if req is None:
        raise AppError("Requirement not found", 404, "requirement_not_found")
    return req


def update_requirement(db: Session, req_id: int, data: RequirementUpdate) -> Requirement:
    req = get_requirement(db, req_id)
    payload = data.model_dump(exclude_unset=True)

    if any(k in payload for k in ("source_document_id", "source_version_id", "source_chunk_id")):
        _validate_source_refs(
            db,
            payload.get("source_document_id", req.source_document_id),
            payload.get("source_version_id", req.source_version_id),
            payload.get("source_chunk_id", req.source_chunk_id),
        )

    for k, v in payload.items():
        setattr(req, k, v)
    db.flush()
    return req


def delete_requirement(db: Session, req_id: int) -> Requirement:
    req = get_requirement(db, req_id)
    req.is_active = False
    db.flush()
    return req


def _detects_cycle(db: Session, requirement_id: int, prerequisite_id: int) -> bool:
    seen: set[int] = set()
    frontier = {prerequisite_id}
    while frontier:
        if requirement_id in frontier:
            return True
        seen |= frontier
        rows = (
            db.query(RequirementPrerequisite.prerequisite_id)
            .filter(RequirementPrerequisite.requirement_id.in_(frontier))
            .all()
        )
        frontier = {row[0] for row in rows} - seen
    return False


def add_prerequisite(
    db: Session, requirement_id: int, prerequisite_id: int
) -> RequirementPrerequisite:
    if requirement_id == prerequisite_id:
        raise AppError("A requirement cannot be its own prerequisite", 400, "self_prereq")

    get_requirement(db, requirement_id)
    get_requirement(db, prerequisite_id)

    existing = (
        db.query(RequirementPrerequisite)
        .filter(
            RequirementPrerequisite.requirement_id == requirement_id,
            RequirementPrerequisite.prerequisite_id == prerequisite_id,
        )
        .first()
    )
    if existing:
        return existing

    if _detects_cycle(db, requirement_id, prerequisite_id):
        raise AppError(
            "Prerequisite would create a cycle", 400, "prereq_cycle"
        )

    link = RequirementPrerequisite(
        requirement_id=requirement_id, prerequisite_id=prerequisite_id
    )
    db.add(link)
    db.flush()
    return link


def remove_prerequisite(db: Session, requirement_id: int, prerequisite_id: int) -> None:
    link = (
        db.query(RequirementPrerequisite)
        .filter(
            RequirementPrerequisite.requirement_id == requirement_id,
            RequirementPrerequisite.prerequisite_id == prerequisite_id,
        )
        .first()
    )
    if link:
        db.delete(link)
        db.flush()


def list_prerequisites(db: Session, requirement_id: int) -> List[int]:
    rows = (
        db.query(RequirementPrerequisite.prerequisite_id)
        .filter(RequirementPrerequisite.requirement_id == requirement_id)
        .all()
    )
    return [row[0] for row in rows]
