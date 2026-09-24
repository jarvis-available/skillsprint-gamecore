from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.job_role import JobRole
from app.models.requirement import Requirement
from app.models.role_requirement import RoleRequirement
from app.schemas.role_requirement import (
    MatrixCell,
    MatrixRow,
    RoleRequirementCreate,
    RoleRequirementUpdate,
)


def _ensure_role(db: Session, role_id: int) -> JobRole:
    role = db.query(JobRole).filter(JobRole.id == role_id).first()
    if role is None:
        raise AppError("Job role not found", 404, "job_role_not_found")
    return role


def _ensure_requirement(db: Session, req_id: int) -> Requirement:
    req = db.query(Requirement).filter(Requirement.id == req_id).first()
    if req is None:
        raise AppError("Requirement not found", 404, "requirement_not_found")
    return req


def assign(
    db: Session, data: RoleRequirementCreate, actor_id: Optional[int]
) -> RoleRequirement:
    _ensure_role(db, data.job_role_id)
    _ensure_requirement(db, data.requirement_id)

    existing = (
        db.query(RoleRequirement)
        .filter(
            RoleRequirement.job_role_id == data.job_role_id,
            RoleRequirement.requirement_id == data.requirement_id,
        )
        .first()
    )
    if existing:
        raise AppError(
            "Requirement already assigned to role", 409, "role_requirement_exists"
        )

    row = RoleRequirement(
        job_role_id=data.job_role_id,
        requirement_id=data.requirement_id,
        is_mandatory=data.is_mandatory,
        priority_override=data.priority_override,
        due_stage_override=data.due_stage_override,
        notes=data.notes,
        created_by=actor_id,
    )
    db.add(row)
    db.flush()
    return row


def update(
    db: Session, link_id: int, data: RoleRequirementUpdate
) -> RoleRequirement:
    row = db.query(RoleRequirement).filter(RoleRequirement.id == link_id).first()
    if row is None:
        raise AppError("Assignment not found", 404, "role_requirement_not_found")
    payload = data.model_dump(exclude_unset=True)
    for k, v in payload.items():
        setattr(row, k, v)
    db.flush()
    return row


def unassign(db: Session, link_id: int) -> None:
    row = db.query(RoleRequirement).filter(RoleRequirement.id == link_id).first()
    if row is None:
        raise AppError("Assignment not found", 404, "role_requirement_not_found")
    db.delete(row)
    db.flush()


def list_for_role(db: Session, role_id: int) -> List[RoleRequirement]:
    _ensure_role(db, role_id)
    return (
        db.query(RoleRequirement)
        .filter(RoleRequirement.job_role_id == role_id)
        .all()
    )


def list_for_requirement(db: Session, requirement_id: int) -> List[RoleRequirement]:
    _ensure_requirement(db, requirement_id)
    return (
        db.query(RoleRequirement)
        .filter(RoleRequirement.requirement_id == requirement_id)
        .all()
    )


def _row_for_role(
    db: Session, role: JobRole
) -> Tuple[List[MatrixCell], int, int]:
    q = (
        db.query(RoleRequirement, Requirement)
        .join(Requirement, RoleRequirement.requirement_id == Requirement.id)
        .filter(
            RoleRequirement.job_role_id == role.id,
            Requirement.is_active.is_(True),
        )
        .order_by(Requirement.req_code.asc())
    )
    cells: List[MatrixCell] = []
    mandatory_count = 0
    for link, req in q.all():
        effective_priority = link.priority_override or req.priority
        effective_due_stage = link.due_stage_override or req.due_stage
        cells.append(
            MatrixCell(
                req_code=req.req_code,
                requirement_id=req.id,
                title=req.title,
                requirement_type=req.requirement_type,
                must_type=req.must_type,
                is_mandatory=link.is_mandatory,
                effective_priority=effective_priority,
                effective_due_stage=effective_due_stage,
                source_document_id=req.source_document_id,
                source_section=req.source_section,
            )
        )
        if link.is_mandatory:
            mandatory_count += 1
    return cells, mandatory_count, len(cells)


def matrix_for_role(db: Session, role_id: int) -> MatrixRow:
    role = _ensure_role(db, role_id)
    cells, mandatory_count, total = _row_for_role(db, role)
    return MatrixRow(
        job_role_id=role.id,
        job_role_name=role.name,
        department=role.department,
        cells=cells,
        mandatory_count=mandatory_count,
        total_count=total,
    )


def full_matrix(db: Session) -> List[MatrixRow]:
    roles = (
        db.query(JobRole)
        .filter(JobRole.is_active.is_(True))
        .order_by(JobRole.name.asc())
        .all()
    )
    out: List[MatrixRow] = []
    for role in roles:
        cells, mandatory_count, total = _row_for_role(db, role)
        out.append(
            MatrixRow(
                job_role_id=role.id,
                job_role_name=role.name,
                department=role.department,
                cells=cells,
                mandatory_count=mandatory_count,
                total_count=total,
            )
        )
    return out
