from typing import Optional

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin_or_manager
from app.core.exceptions import AppError
from app.database.connection import get_db
from app.models.user import User
from app.schemas.validation import (
    ComparisonOut,
    FindingOut,
    ValidationRunDetail,
    ValidationRunSummary,
)
from app.services import audit_service, validation_service


router = APIRouter(prefix="/api", tags=["validation"])


def _client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


@router.post(
    "/plans/{plan_id}/validate",
    response_model=ValidationRunDetail,
    status_code=status.HTTP_201_CREATED,
)
def validate_plan(
    plan_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin_or_manager),
):
    run = validation_service.validate_plan(db, plan_id, current.id)
    audit_service.record(
        db,
        current.id,
        "plan.validate",
        "onboarding_plan",
        plan_id,
        details=f"run={run.id} status={run.final_status}",
        ip_address=_client_ip(request),
    )
    db.commit()

    findings = validation_service.list_findings(db, run.id)
    comparisons = validation_service.list_comparisons(db, run.id)
    payload = ValidationRunSummary.model_validate(run).model_dump()
    payload["summary_json"] = run.summary_json
    payload["findings"] = [FindingOut.model_validate(f) for f in findings]
    payload["comparisons"] = [ComparisonOut.model_validate(c) for c in comparisons]
    return ValidationRunDetail.model_validate(payload)


@router.get("/plans/{plan_id}/validation-runs")
def list_runs(
    plan_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    from app.models.onboarding_plan import OnboardingPlan

    plan = db.query(OnboardingPlan).filter(OnboardingPlan.id == plan_id).first()
    if plan is None:
        raise AppError("Plan not found", 404, "plan_not_found")
    if current.system_role not in ("admin", "training_manager", "reviewer"):
        if plan.employee_user_id != current.id:
            raise AppError("Not authorized", 403, "forbidden")

    runs = validation_service.list_runs_for_plan(db, plan_id)
    return {"items": [ValidationRunSummary.model_validate(r) for r in runs]}


@router.get("/validation-runs/{run_id}", response_model=ValidationRunDetail)
def get_run(
    run_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    from app.models.onboarding_plan import OnboardingPlan

    run = validation_service.get_run(db, run_id)
    plan = db.query(OnboardingPlan).filter(OnboardingPlan.id == run.plan_id).first()
    if plan and current.system_role not in ("admin", "training_manager", "reviewer"):
        if plan.employee_user_id != current.id:
            raise AppError("Not authorized", 403, "forbidden")

    findings = validation_service.list_findings(db, run.id)
    comparisons = validation_service.list_comparisons(db, run.id)
    payload = ValidationRunSummary.model_validate(run).model_dump()
    payload["summary_json"] = run.summary_json
    payload["findings"] = [FindingOut.model_validate(f) for f in findings]
    payload["comparisons"] = [ComparisonOut.model_validate(c) for c in comparisons]
    return ValidationRunDetail.model_validate(payload)
