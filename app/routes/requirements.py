from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin_or_manager
from app.database.connection import get_db
from app.models.user import User
from app.schemas.requirement import (
    PrerequisiteLink,
    RequirementCreate,
    RequirementOut,
    RequirementUpdate,
    RequirementWithPrereqs,
)
from app.services import audit_service, requirement_service


router = APIRouter(prefix="/api/requirements", tags=["requirements"])


def _client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


def _to_out(req) -> RequirementOut:
    payload = {
        c.name: getattr(req, c.name) for c in req.__table__.columns
    }
    payload["is_mandatory_derived"] = requirement_service.is_mandatory_derived(
        req.must_type
    )
    return RequirementOut.model_validate(payload)


@router.get("")
def list_requirements(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: Optional[str] = None,
    requirement_type: Optional[str] = None,
    must_type: Optional[str] = None,
    source_document_id: Optional[int] = None,
    include_inactive: bool = False,
):
    items, total = requirement_service.list_requirements(
        db,
        skip=skip,
        limit=limit,
        search=search,
        requirement_type=requirement_type,
        must_type=must_type,
        source_document_id=source_document_id,
        include_inactive=include_inactive,
    )
    return {
        "total": total,
        "items": [_to_out(r) for r in items],
    }


@router.post("", response_model=RequirementOut, status_code=status.HTTP_201_CREATED)
def create_requirement(
    payload: RequirementCreate,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin_or_manager),
):
    req = requirement_service.create_requirement(db, payload, current.id)
    audit_service.record(
        db,
        current.id,
        "requirement.create",
        "requirement",
        req.id,
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(req)
    return _to_out(req)


@router.get("/{req_id}", response_model=RequirementWithPrereqs)
def get_requirement(
    req_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    req = requirement_service.get_requirement(db, req_id)
    prereqs = requirement_service.list_prerequisites(db, req_id)
    base = _to_out(req).model_dump()
    base["prerequisite_ids"] = prereqs
    return RequirementWithPrereqs.model_validate(base)


@router.put("/{req_id}", response_model=RequirementOut)
def update_requirement(
    req_id: int,
    payload: RequirementUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin_or_manager),
):
    req = requirement_service.update_requirement(db, req_id, payload)
    audit_service.record(
        db,
        current.id,
        "requirement.update",
        "requirement",
        req.id,
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(req)
    return _to_out(req)


@router.delete("/{req_id}")
def delete_requirement(
    req_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin_or_manager),
):
    requirement_service.delete_requirement(db, req_id)
    audit_service.record(
        db,
        current.id,
        "requirement.deactivate",
        "requirement",
        req_id,
        ip_address=_client_ip(request),
    )
    db.commit()
    return {"detail": "requirement_deactivated"}


@router.post("/{req_id}/prerequisites", status_code=status.HTTP_201_CREATED)
def add_prereq(
    req_id: int,
    payload: PrerequisiteLink,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin_or_manager),
):
    requirement_service.add_prerequisite(db, req_id, payload.prerequisite_id)
    audit_service.record(
        db,
        current.id,
        "requirement.prereq.add",
        "requirement",
        req_id,
        details=f"prerequisite_id={payload.prerequisite_id}",
        ip_address=_client_ip(request),
    )
    db.commit()
    return {"detail": "prerequisite_added"}


@router.delete("/{req_id}/prerequisites/{prereq_id}")
def remove_prereq(
    req_id: int,
    prereq_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin_or_manager),
):
    requirement_service.remove_prerequisite(db, req_id, prereq_id)
    audit_service.record(
        db,
        current.id,
        "requirement.prereq.remove",
        "requirement",
        req_id,
        details=f"prerequisite_id={prereq_id}",
        ip_address=_client_ip(request),
    )
    db.commit()
    return {"detail": "prerequisite_removed"}
