from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin_or_manager
from app.core.exceptions import AppError
from app.database.connection import get_db
from app.models.user import User
from app.schemas.plan import GenerateRequest, PlanDetail
from app.services import audit_service, generation_service, plan_service


router = APIRouter(prefix="/api/plans", tags=["plans"])


def _client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


@router.get("")
def list_plans(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    employee_user_id: Optional[int] = None,
    job_role_id: Optional[int] = None,
    status_filter: Optional[str] = Query(default=None, alias="status"),
):
    if current.system_role not in ("admin", "training_manager", "reviewer"):
        employee_user_id = current.id

    items, total = plan_service.list_plans(
        db,
        skip=skip,
        limit=limit,
        employee_user_id=employee_user_id,
        job_role_id=job_role_id,
        status=status_filter,
    )
    return {"total": total, "items": items}


@router.post("/generate", response_model=PlanDetail, status_code=status.HTTP_201_CREATED)
def generate_plan(
    payload: GenerateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin_or_manager),
):
    plan, run = generation_service.generate_plan(
        db,
        employee_user_id=payload.employee_user_id,
        job_role_id=payload.job_role_id,
        max_chunks=payload.max_chunks,
        triggered_by=current.id,
        plan_note=payload.plan_note,
    )
    audit_service.record(
        db,
        current.id,
        "plan.generate",
        "onboarding_plan",
        plan.id,
        details=f"run={run.id}",
        ip_address=_client_ip(request),
    )
    db.commit()
    return PlanDetail.model_validate(plan_service.get_plan_detail(db, plan.id))


@router.get("/{plan_id}", response_model=PlanDetail)
def get_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    detail = plan_service.get_plan_detail(db, plan_id)
    if current.system_role not in ("admin", "training_manager", "reviewer"):
        if detail["employee_user_id"] != current.id:
            raise AppError("Not authorized to view this plan", 403, "plan_forbidden")
    return PlanDetail.model_validate(detail)


@router.delete("/{plan_id}")
def archive_plan(
    plan_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin_or_manager),
):
    plan_service.archive_plan(db, plan_id)
    audit_service.record(
        db,
        current.id,
        "plan.archive",
        "onboarding_plan",
        plan_id,
        ip_address=_client_ip(request),
    )
    db.commit()
    return {"detail": "plan_archived"}
