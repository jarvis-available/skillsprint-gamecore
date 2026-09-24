from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin_or_manager
from app.database.connection import get_db
from app.models.user import User
from app.schemas.role_requirement import (
    MatrixRow,
    RoleRequirementCreate,
    RoleRequirementOut,
    RoleRequirementUpdate,
)
from app.services import audit_service, role_requirement_service


router = APIRouter(prefix="/api/role-matrix", tags=["role-matrix"])


def _client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


@router.get("")
def full_matrix(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    rows = role_requirement_service.full_matrix(db)
    return {"rows": [r.model_dump() for r in rows]}


@router.get("/roles/{role_id}", response_model=MatrixRow)
def matrix_for_role(
    role_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return role_requirement_service.matrix_for_role(db, role_id)


@router.get("/assignments")
def list_assignments(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    job_role_id: Optional[int] = Query(default=None),
    requirement_id: Optional[int] = Query(default=None),
):
    if job_role_id is not None:
        rows = role_requirement_service.list_for_role(db, job_role_id)
    elif requirement_id is not None:
        rows = role_requirement_service.list_for_requirement(db, requirement_id)
    else:
        rows = []
    return {"items": [RoleRequirementOut.model_validate(r) for r in rows]}


@router.post("/assignments", response_model=RoleRequirementOut, status_code=status.HTTP_201_CREATED)
def assign(
    payload: RoleRequirementCreate,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin_or_manager),
):
    row = role_requirement_service.assign(db, payload, current.id)
    audit_service.record(
        db,
        current.id,
        "role_requirement.assign",
        "role_requirement",
        row.id,
        details=f"role={payload.job_role_id},req={payload.requirement_id}",
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(row)
    return row


@router.put("/assignments/{link_id}", response_model=RoleRequirementOut)
def update(
    link_id: int,
    payload: RoleRequirementUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin_or_manager),
):
    row = role_requirement_service.update(db, link_id, payload)
    audit_service.record(
        db,
        current.id,
        "role_requirement.update",
        "role_requirement",
        link_id,
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(row)
    return row


@router.delete("/assignments/{link_id}")
def unassign(
    link_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin_or_manager),
):
    role_requirement_service.unassign(db, link_id)
    audit_service.record(
        db,
        current.id,
        "role_requirement.unassign",
        "role_requirement",
        link_id,
        ip_address=_client_ip(request),
    )
    db.commit()
    return {"detail": "assignment_removed"}
