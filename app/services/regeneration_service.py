from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.onboarding_plan import OnboardingPlan
from app.models.policy_impact import PolicyImpact
from app.services import generation_service, impact_service


def regenerate_impact_plans(
    db: Session,
    impact_id: int,
    triggered_by: Optional[int],
    max_chunks: int = 40,
) -> Dict:
    impact = impact_service.get_impact(db, impact_id)
    plan_ids = impact_service.parse_plan_ids(impact)
    if not plan_ids:
        impact_service.mark_regenerated(db, impact_id)
        return {"impact_id": impact_id, "regenerated": [], "failed": [], "skipped": []}

    regenerated: List[Dict] = []
    failed: List[Dict] = []
    skipped: List[Dict] = []

    for plan_id in plan_ids:
        old_plan = (
            db.query(OnboardingPlan).filter(OnboardingPlan.id == plan_id).first()
        )
        if old_plan is None:
            skipped.append({"plan_id": plan_id, "reason": "plan_not_found"})
            continue
        if old_plan.status == "archived":
            skipped.append({"plan_id": plan_id, "reason": "already_archived"})
            continue

        try:
            new_plan, run = generation_service.generate_plan(
                db,
                employee_user_id=old_plan.employee_user_id,
                job_role_id=old_plan.job_role_id,
                max_chunks=max_chunks,
                triggered_by=triggered_by,
                plan_note=(
                    f"regenerated from impact#{impact_id} of document#{impact.document_id}"
                ),
            )
            old_plan.status = "archived"
            db.flush()
            regenerated.append(
                {
                    "old_plan_id": plan_id,
                    "new_plan_id": new_plan.id,
                    "generation_run_id": run.id,
                    "status": new_plan.status,
                }
            )
        except Exception as exc:
            failed.append({"plan_id": plan_id, "error": str(exc)[:500]})

    impact_service.mark_regenerated(db, impact_id)

    return {
        "impact_id": impact_id,
        "regenerated": regenerated,
        "failed": failed,
        "skipped": skipped,
    }


def regenerate_single_plan(
    db: Session,
    plan_id: int,
    triggered_by: Optional[int],
    max_chunks: int = 40,
    note: Optional[str] = None,
) -> Dict:
    old_plan = db.query(OnboardingPlan).filter(OnboardingPlan.id == plan_id).first()
    if old_plan is None:
        raise AppError("Plan not found", 404, "plan_not_found")

    new_plan, run = generation_service.generate_plan(
        db,
        employee_user_id=old_plan.employee_user_id,
        job_role_id=old_plan.job_role_id,
        max_chunks=max_chunks,
        triggered_by=triggered_by,
        plan_note=note or f"regenerated from plan#{plan_id}",
    )
    old_plan.status = "archived"
    db.flush()

    return {
        "old_plan_id": plan_id,
        "new_plan_id": new_plan.id,
        "generation_run_id": run.id,
        "status": new_plan.status,
    }
