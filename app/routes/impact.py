from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin_or_manager
from app.database.connection import get_db
from app.models.user import User
from app.services import audit_service, impact_service, regeneration_service


router = APIRouter(prefix="/api", tags=["impact"])


def _client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


def _serialize_impact(impact) -> dict:
    return {
        "id": impact.id,
        "document_id": impact.document_id,
        "from_version_id": impact.from_version_id,
        "to_version_id": impact.to_version_id,
        "status": impact.status,
        "affected_plan_ids": impact.affected_plan_ids,
        "affected_module_ids": impact.affected_module_ids,
        "affected_task_ids": impact.affected_task_ids,
        "affected_quiz_question_ids": impact.affected_quiz_question_ids,
        "affected_assessment_ids": impact.affected_assessment_ids,
        "affected_employee_user_ids": impact.affected_employee_user_ids,
        "summary_json": impact.summary_json,
        "created_at": impact.created_at,
    }


@router.post(
    "/documents/{document_id}/impact",
    status_code=status.HTTP_201_CREATED,
)
def analyze_impact(
    document_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin_or_manager),
):
    impact = impact_service.analyze_document_impact(db, document_id, current.id)
    audit_service.record(
        db,
        current.id,
        "policy.impact.analyze",
        "document",
        document_id,
        details=f"impact#{impact.id}",
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(impact)
    return _serialize_impact(impact)


@router.get("/policy-impacts")
def list_impacts(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    document_id: Optional[int] = Query(default=None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    rows = impact_service.list_impacts(db, document_id, skip, limit)
    return {"items": [_serialize_impact(r) for r in rows]}


@router.get("/policy-impacts/{impact_id}")
def get_impact(
    impact_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return _serialize_impact(impact_service.get_impact(db, impact_id))


@router.post("/policy-impacts/{impact_id}/regenerate")
def regenerate_impact(
    impact_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin_or_manager),
    max_chunks: int = Query(40, ge=5, le=200),
):
    result = regeneration_service.regenerate_impact_plans(
        db, impact_id, current.id, max_chunks
    )
    audit_service.record(
        db,
        current.id,
        "policy.impact.regenerate",
        "policy_impact",
        impact_id,
        details=(
            f"regenerated={len(result['regenerated'])} "
            f"failed={len(result['failed'])} skipped={len(result['skipped'])}"
        ),
        ip_address=_client_ip(request),
    )
    db.commit()
    return result


@router.post("/policy-impacts/{impact_id}/dismiss")
def dismiss_impact(
    impact_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin_or_manager),
):
    impact_service.mark_dismissed(db, impact_id)
    audit_service.record(
        db,
        current.id,
        "policy.impact.dismiss",
        "policy_impact",
        impact_id,
        ip_address=_client_ip(request),
    )
    db.commit()
    return {"detail": "impact_dismissed"}


@router.post("/plans/{plan_id}/regenerate")
def regenerate_plan(
    plan_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin_or_manager),
    max_chunks: int = Query(40, ge=5, le=200),
):
    result = regeneration_service.regenerate_single_plan(
        db, plan_id, current.id, max_chunks
    )
    audit_service.record(
        db,
        current.id,
        "plan.regenerate",
        "onboarding_plan",
        plan_id,
        details=f"new_plan={result['new_plan_id']}",
        ip_address=_client_ip(request),
    )
    db.commit()
    return result
