from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin
from app.database.connection import get_db
from app.models.user import User
from app.schemas.job_role import JobRoleCreate, JobRoleOut, JobRoleUpdate
from app.services import audit_service, job_role_service


router = APIRouter(prefix="/api/job-roles", tags=["job-roles"])


def _client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


@router.get("")
def list_roles(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: Optional[str] = None,
    include_inactive: bool = False,
):
    items, total = job_role_service.list_job_roles(
        db, skip, limit, search, active_only=not include_inactive
    )
    return {
        "total": total,
        "items": [JobRoleOut.model_validate(r) for r in items],
    }


@router.post("", response_model=JobRoleOut, status_code=status.HTTP_201_CREATED)
def create_role(
    payload: JobRoleCreate,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin),
):
    role = job_role_service.create_job_role(db, payload)
    audit_service.record(
        db,
        current.id,
        "job_role.create",
        "job_role",
        role.id,
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(role)
    return role


@router.get("/{role_id}", response_model=JobRoleOut)
def get_role(
    role_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return job_role_service.get_job_role(db, role_id)


@router.put("/{role_id}", response_model=JobRoleOut)
def update_role(
    role_id: int,
    payload: JobRoleUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin),
):
    role = job_role_service.update_job_role(db, role_id, payload)
    audit_service.record(
        db,
        current.id,
        "job_role.update",
        "job_role",
        role.id,
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(role)
    return role


@router.delete("/{role_id}")
def delete_role(
    role_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin),
):
    job_role_service.delete_job_role(db, role_id)
    audit_service.record(
        db,
        current.id,
        "job_role.deactivate",
        "job_role",
        role_id,
        ip_address=_client_ip(request),
    )
    db.commit()
    return {"detail": "job_role_deactivated"}
