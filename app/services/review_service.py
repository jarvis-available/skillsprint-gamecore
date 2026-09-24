from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.onboarding_plan import OnboardingPlan
from app.models.review import FindingReview, PlanReview
from app.models.validation import ValidationFinding
from app.schemas.review import FindingReviewCreate, PlanReviewCreate


def review_finding(
    db: Session,
    finding_id: int,
    data: FindingReviewCreate,
    reviewer_id: int,
) -> FindingReview:
    finding = (
        db.query(ValidationFinding)
        .filter(ValidationFinding.id == finding_id)
        .first()
    )
    if finding is None:
        raise AppError("Finding not found", 404, "finding_not_found")

    prior_severity = finding.severity
    if data.override_severity and data.override_severity != finding.severity:
        finding.severity = data.override_severity

    review = FindingReview(
        finding_id=finding_id,
        reviewed_by=reviewer_id,
        decision=data.decision,
        comment=data.comment,
        override_severity=data.override_severity,
        prior_severity=prior_severity,
    )
    db.add(review)
    db.flush()
    return review


def list_finding_reviews(
    db: Session, finding_id: int
) -> List[FindingReview]:
    return (
        db.query(FindingReview)
        .filter(FindingReview.finding_id == finding_id)
        .order_by(FindingReview.created_at.desc())
        .all()
    )


def review_plan(
    db: Session,
    plan_id: int,
    data: PlanReviewCreate,
    reviewer_id: int,
) -> PlanReview:
    plan = db.query(OnboardingPlan).filter(OnboardingPlan.id == plan_id).first()
    if plan is None:
        raise AppError("Plan not found", 404, "plan_not_found")

    prior_status = plan.status
    new_status: Optional[str] = None

    if data.decision == "approve":
        new_status = data.new_status or "verified"
    elif data.decision == "reject":
        new_status = "manual_review_required"
    elif data.decision == "mark_manual_review":
        new_status = "manual_review_required"
    elif data.decision == "request_regeneration":
        new_status = "draft"
    elif data.decision == "override_status":
        if not data.new_status:
            raise AppError(
                "new_status is required for override_status",
                400,
                "missing_new_status",
            )
        new_status = data.new_status
    elif data.decision == "comment":
        new_status = None

    if new_status is not None:
        plan.status = new_status

    review = PlanReview(
        plan_id=plan_id,
        validation_run_id=data.validation_run_id,
        reviewed_by=reviewer_id,
        decision=data.decision,
        comment=data.comment,
        prior_status=prior_status,
        new_status=new_status,
    )
    db.add(review)
    db.flush()
    return review


def list_plan_reviews(db: Session, plan_id: int) -> List[PlanReview]:
    return (
        db.query(PlanReview)
        .filter(PlanReview.plan_id == plan_id)
        .order_by(PlanReview.created_at.desc())
        .all()
    )


def list_flagged_findings(
    db: Session,
    plan_id: Optional[int] = None,
    severity: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[ValidationFinding]:
    from app.models.validation import ValidationRun

    q = db.query(ValidationFinding).join(
        ValidationRun, ValidationFinding.validation_run_id == ValidationRun.id
    )
    if plan_id is not None:
        q = q.filter(ValidationRun.plan_id == plan_id)
    if severity:
        q = q.filter(ValidationFinding.severity == severity)
    return q.order_by(ValidationFinding.created_at.desc()).offset(skip).limit(limit).all()
