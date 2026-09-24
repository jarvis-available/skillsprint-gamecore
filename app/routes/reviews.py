from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.deps import require_reviewer
from app.database.connection import get_db
from app.models.user import User
from app.schemas.review import (
    FindingReviewCreate,
    FindingReviewOut,
    PlanReviewCreate,
    PlanReviewOut,
)
from app.services import audit_service, review_service


router = APIRouter(prefix="/api", tags=["reviews"])


def _client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


@router.post(
    "/validation-findings/{finding_id}/reviews",
    response_model=FindingReviewOut,
    status_code=status.HTTP_201_CREATED,
)
def create_finding_review(
    finding_id: int,
    payload: FindingReviewCreate,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(require_reviewer),
):
    review = review_service.review_finding(db, finding_id, payload, current.id)
    audit_service.record(
        db,
        current.id,
        "finding.review",
        "validation_finding",
        finding_id,
        details=(
            f"decision={payload.decision} override={payload.override_severity or ''}"
        ),
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(review)
    return review


@router.get("/validation-findings/{finding_id}/reviews")
def list_finding_reviews(
    finding_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_reviewer),
):
    rows = review_service.list_finding_reviews(db, finding_id)
    return {"items": [FindingReviewOut.model_validate(r) for r in rows]}


@router.post(
    "/plans/{plan_id}/reviews",
    response_model=PlanReviewOut,
    status_code=status.HTTP_201_CREATED,
)
def create_plan_review(
    plan_id: int,
    payload: PlanReviewCreate,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(require_reviewer),
):
    review = review_service.review_plan(db, plan_id, payload, current.id)
    audit_service.record(
        db,
        current.id,
        "plan.review",
        "onboarding_plan",
        plan_id,
        details=(
            f"decision={payload.decision} prior={review.prior_status} new={review.new_status or ''}"
        ),
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(review)
    return review


@router.get("/plans/{plan_id}/reviews")
def list_plan_reviews(
    plan_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_reviewer),
):
    rows = review_service.list_plan_reviews(db, plan_id)
    return {"items": [PlanReviewOut.model_validate(r) for r in rows]}


@router.get("/review-queue")
def review_queue(
    db: Session = Depends(get_db),
    _: User = Depends(require_reviewer),
    plan_id: Optional[int] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
):
    rows = review_service.list_flagged_findings(db, plan_id, severity, skip, limit)
    return {
        "items": [
            {
                "id": r.id,
                "validation_run_id": r.validation_run_id,
                "entity_type": r.entity_type,
                "entity_id": r.entity_id,
                "entity_code": r.entity_code,
                "issue_type": r.issue_type,
                "severity": r.severity,
                "message": r.message,
                "source_reference": r.source_reference,
                "score": r.score,
                "created_at": r.created_at,
            }
            for r in rows
        ]
    }
