from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.exceptions import AppError
from app.database.connection import get_db
from app.models.onboarding_plan import OnboardingPlan
from app.models.user import User
from app.schemas.progress import (
    AssessmentAttemptOut,
    AssessmentAttemptSubmission,
    ChecklistToggle,
    CompletionUpdate,
    PlanProgressSummary,
    QuizAttemptOut,
    QuizAttemptSubmission,
    RecommendationOut,
    RecommendationUpdate,
)
from app.services import audit_service, progress_service


router = APIRouter(prefix="/api", tags=["progress"])


def _client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


def _owner_or_privileged(current: User, employee_user_id: int) -> None:
    if current.system_role in ("admin", "training_manager", "reviewer", "manager"):
        return
    if current.id != employee_user_id:
        raise AppError("Not authorized", 403, "forbidden")


def _plan_owner(db: Session, plan_id: int, current: User) -> OnboardingPlan:
    plan = db.query(OnboardingPlan).filter(OnboardingPlan.id == plan_id).first()
    if plan is None:
        raise AppError("Plan not found", 404, "plan_not_found")
    _owner_or_privileged(current, plan.employee_user_id)
    return plan


@router.post("/modules/{module_id}/completion", status_code=status.HTTP_200_OK)
def set_module_completion(
    module_id: int,
    payload: CompletionUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    from app.models.learning_module import LearningModule

    module = db.query(LearningModule).filter(LearningModule.id == module_id).first()
    if module is None:
        raise AppError("Module not found", 404, "module_not_found")
    plan = _plan_owner(db, module.plan_id, current)

    row = progress_service.upsert_module_completion(
        db, module_id, plan.employee_user_id, payload.status, payload.notes
    )
    audit_service.record(
        db,
        current.id,
        "module.completion",
        "learning_module",
        module_id,
        details=f"status={payload.status}",
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(row)
    return {
        "id": row.id,
        "module_id": row.module_id,
        "status": row.status,
        "completed_at": row.completed_at,
    }


@router.post("/tasks/{task_id}/completion")
def set_task_completion(
    task_id: int,
    payload: CompletionUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    from app.models.plan_task import PlanTask

    task = db.query(PlanTask).filter(PlanTask.id == task_id).first()
    if task is None:
        raise AppError("Task not found", 404, "task_not_found")
    plan = _plan_owner(db, task.plan_id, current)

    row = progress_service.upsert_task_completion(
        db,
        task_id,
        plan.employee_user_id,
        payload.status,
        payload.completion_notes,
        payload.evidence_url,
    )
    audit_service.record(
        db,
        current.id,
        "task.completion",
        "plan_task",
        task_id,
        details=f"status={payload.status}",
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(row)
    return {
        "id": row.id,
        "task_id": row.task_id,
        "status": row.status,
        "completed_at": row.completed_at,
    }


@router.post("/checklist-items/{item_id}/toggle")
def toggle_checklist_item(
    item_id: int,
    payload: ChecklistToggle,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    from app.models.checklist import Checklist, ChecklistItem

    item = db.query(ChecklistItem).filter(ChecklistItem.id == item_id).first()
    if item is None:
        raise AppError("Checklist item not found", 404, "checklist_item_not_found")
    checklist = db.query(Checklist).filter(Checklist.id == item.checklist_id).first()
    plan = _plan_owner(db, checklist.plan_id, current)

    row = progress_service.toggle_checklist_item(
        db, item_id, plan.employee_user_id, payload.checked
    )
    audit_service.record(
        db,
        current.id,
        "checklist.toggle",
        "checklist_item",
        item_id,
        details=f"checked={payload.checked}",
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(row)
    return {"id": row.id, "checked": row.checked, "completed_at": row.completed_at}


@router.post(
    "/quizzes/{quiz_id}/attempts",
    response_model=QuizAttemptOut,
    status_code=status.HTTP_201_CREATED,
)
def submit_quiz_attempt(
    quiz_id: int,
    payload: QuizAttemptSubmission,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    from app.models.quiz import Quiz

    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if quiz is None:
        raise AppError("Quiz not found", 404, "quiz_not_found")
    plan = _plan_owner(db, quiz.plan_id, current)

    answers = [a.model_dump() for a in payload.answers]
    attempt = progress_service.submit_quiz_attempt(
        db, quiz_id, plan.employee_user_id, answers
    )
    audit_service.record(
        db,
        current.id,
        "quiz.attempt",
        "quiz",
        quiz_id,
        details=f"score={attempt.percentage} passed={attempt.passed}",
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(attempt)
    return attempt


@router.get("/quizzes/{quiz_id}/attempts")
def list_quiz_attempts(
    quiz_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    from app.models.attempt import QuizAttempt
    from app.models.quiz import Quiz

    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if quiz is None:
        raise AppError("Quiz not found", 404, "quiz_not_found")
    plan = _plan_owner(db, quiz.plan_id, current)
    q = db.query(QuizAttempt).filter(
        QuizAttempt.quiz_id == quiz_id,
        QuizAttempt.employee_user_id == plan.employee_user_id,
    )
    rows = q.order_by(QuizAttempt.submitted_at.desc()).all()
    return {"items": [QuizAttemptOut.model_validate(a) for a in rows]}


@router.post(
    "/assessments/{assessment_id}/attempts",
    response_model=AssessmentAttemptOut,
    status_code=status.HTTP_201_CREATED,
)
def submit_assessment_attempt(
    assessment_id: int,
    payload: AssessmentAttemptSubmission,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    from app.models.assessment import Assessment

    assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    if assessment is None:
        raise AppError("Assessment not found", 404, "assessment_not_found")
    plan = _plan_owner(db, assessment.plan_id, current)

    scores = [s.model_dump() for s in payload.rubric_scores]
    attempt = progress_service.submit_assessment_attempt(
        db,
        assessment_id,
        plan.employee_user_id,
        scores,
        payload.notes,
        current.id,
    )
    audit_service.record(
        db,
        current.id,
        "assessment.attempt",
        "assessment",
        assessment_id,
        details=f"score={attempt.percentage} passed={attempt.passed}",
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(attempt)
    return attempt


@router.get("/plans/{plan_id}/progress", response_model=PlanProgressSummary)
def get_progress(
    plan_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    plan = _plan_owner(db, plan_id, current)
    data = progress_service.compute_progress(db, plan_id, plan.employee_user_id)
    return PlanProgressSummary.model_validate(data)


@router.post("/plans/{plan_id}/recommendations/generate")
def generate_recommendations(
    plan_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    plan = _plan_owner(db, plan_id, current)
    created = progress_service.generate_recommendations(
        db, plan_id, plan.employee_user_id
    )
    audit_service.record(
        db,
        current.id,
        "recommendations.generate",
        "onboarding_plan",
        plan_id,
        details=f"created={len(created)}",
        ip_address=_client_ip(request),
    )
    db.commit()
    return {
        "created": len(created),
        "items": [RecommendationOut.model_validate(r) for r in created],
    }


@router.get("/plans/{plan_id}/recommendations")
def list_recommendations(
    plan_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
    status_filter: Optional[str] = Query(default=None, alias="status"),
):
    plan = _plan_owner(db, plan_id, current)
    rows = progress_service.list_recommendations(
        db, plan_id, plan.employee_user_id, status_filter
    )
    return {"items": [RecommendationOut.model_validate(r) for r in rows]}


@router.put("/recommendations/{rec_id}")
def update_recommendation(
    rec_id: int,
    payload: RecommendationUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    from app.models.attempt import LearningRecommendation

    rec = (
        db.query(LearningRecommendation)
        .filter(LearningRecommendation.id == rec_id)
        .first()
    )
    if rec is None:
        raise AppError("Recommendation not found", 404, "recommendation_not_found")
    _owner_or_privileged(current, rec.employee_user_id)
    updated = progress_service.update_recommendation(db, rec_id, payload.status)
    audit_service.record(
        db,
        current.id,
        "recommendation.update",
        "learning_recommendation",
        rec_id,
        details=f"status={payload.status}",
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(updated)
    return RecommendationOut.model_validate(updated)
