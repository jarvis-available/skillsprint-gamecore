from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.assessment import Assessment, AssessmentRubric
from app.models.checklist import Checklist, ChecklistItem
from app.models.generation_run import GenerationRun
from app.models.job_role import JobRole
from app.models.learning_module import (
    LearningModule,
    LearningObjective,
    ModuleActivity,
)
from app.models.onboarding_plan import OnboardingPlan, PlanStage
from app.models.plan_task import PlanTask
from app.models.quiz import Quiz, QuizOption, QuizQuestion
from app.models.user import User


def list_plans(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 50,
    employee_user_id: Optional[int] = None,
    job_role_id: Optional[int] = None,
    status: Optional[str] = None,
) -> Tuple[List[dict], int]:
    q = db.query(OnboardingPlan)
    if employee_user_id is not None:
        q = q.filter(OnboardingPlan.employee_user_id == employee_user_id)
    if job_role_id is not None:
        q = q.filter(OnboardingPlan.job_role_id == job_role_id)
    if status:
        q = q.filter(OnboardingPlan.status == status)

    total = q.count()
    plans = q.order_by(OnboardingPlan.created_at.desc()).offset(skip).limit(limit).all()

    if not plans:
        return [], total

    ids = [p.id for p in plans]
    module_counts = dict(
        db.query(LearningModule.plan_id, LearningModule.id)
        .filter(LearningModule.plan_id.in_(ids))
        .all()
    )
    module_counts_map = {}
    for p_id in ids:
        module_counts_map[p_id] = (
            db.query(LearningModule).filter(LearningModule.plan_id == p_id).count()
        )
    task_counts_map = {
        p_id: db.query(PlanTask).filter(PlanTask.plan_id == p_id).count()
        for p_id in ids
    }
    quiz_counts_map = {
        p_id: db.query(Quiz).filter(Quiz.plan_id == p_id).count() for p_id in ids
    }
    assessment_counts_map = {
        p_id: db.query(Assessment).filter(Assessment.plan_id == p_id).count()
        for p_id in ids
    }

    employee_ids = {p.employee_user_id for p in plans}
    role_ids = {p.job_role_id for p in plans}
    employees = {
        u.id: u
        for u in db.query(User).filter(User.id.in_(employee_ids)).all()
    }
    roles = {
        r.id: r
        for r in db.query(JobRole).filter(JobRole.id.in_(role_ids)).all()
    }

    items: List[dict] = []
    for p in plans:
        items.append(
            {
                "id": p.id,
                "plan_code": p.plan_code,
                "employee_user_id": p.employee_user_id,
                "employee_name": employees.get(p.employee_user_id).name
                if employees.get(p.employee_user_id)
                else None,
                "job_role_id": p.job_role_id,
                "job_role_name": roles.get(p.job_role_id).name
                if roles.get(p.job_role_id)
                else None,
                "status": p.status,
                "module_count": module_counts_map.get(p.id, 0),
                "task_count": task_counts_map.get(p.id, 0),
                "quiz_count": quiz_counts_map.get(p.id, 0),
                "assessment_count": assessment_counts_map.get(p.id, 0),
                "created_at": p.created_at,
            }
        )
    return items, total


def _module_payload(db: Session, module: LearningModule) -> dict:
    objectives = (
        db.query(LearningObjective)
        .filter(LearningObjective.module_id == module.id)
        .order_by(LearningObjective.order_index.asc())
        .all()
    )
    activities = (
        db.query(ModuleActivity)
        .filter(ModuleActivity.module_id == module.id)
        .order_by(ModuleActivity.order_index.asc())
        .all()
    )
    return {
        "id": module.id,
        "module_code": module.module_code,
        "title": module.title,
        "purpose": module.purpose,
        "key_concepts": module.key_concepts,
        "estimated_minutes": module.estimated_minutes,
        "completion_criteria": module.completion_criteria,
        "stage_id": module.stage_id,
        "requirement_id": module.requirement_id,
        "is_mandatory": module.is_mandatory,
        "source_document_id": module.source_document_id,
        "source_section": module.source_section,
        "source_chunk_ids": module.source_chunk_ids,
        "order_index": module.order_index,
        "objectives": [
            {"id": o.id, "text": o.text, "order_index": o.order_index}
            for o in objectives
        ],
        "activities": [
            {"id": a.id, "description": a.description, "order_index": a.order_index}
            for a in activities
        ],
    }


def _checklist_payload(db: Session, checklist: Checklist) -> dict:
    items = (
        db.query(ChecklistItem)
        .filter(ChecklistItem.checklist_id == checklist.id)
        .order_by(ChecklistItem.order_index.asc())
        .all()
    )
    return {
        "id": checklist.id,
        "title": checklist.title,
        "description": checklist.description,
        "stage_id": checklist.stage_id,
        "order_index": checklist.order_index,
        "items": [
            {
                "id": i.id,
                "activity": i.activity,
                "is_required": i.is_required,
                "due_stage": i.due_stage,
                "source_document_id": i.source_document_id,
                "source_section": i.source_section,
                "responsible_role": i.responsible_role,
                "order_index": i.order_index,
            }
            for i in items
        ],
    }


def _quiz_payload(db: Session, quiz: Quiz) -> dict:
    questions = (
        db.query(QuizQuestion)
        .filter(QuizQuestion.quiz_id == quiz.id)
        .order_by(QuizQuestion.order_index.asc())
        .all()
    )
    q_list = []
    for q in questions:
        options = (
            db.query(QuizOption)
            .filter(QuizOption.question_id == q.id)
            .order_by(QuizOption.order_index.asc())
            .all()
        )
        q_list.append(
            {
                "id": q.id,
                "question_type": q.question_type,
                "prompt_text": q.prompt_text,
                "difficulty": q.difficulty,
                "source_document_id": q.source_document_id,
                "source_section": q.source_section,
                "explanation": q.explanation,
                "points": q.points,
                "order_index": q.order_index,
                "options": [
                    {
                        "id": o.id,
                        "text": o.text,
                        "is_correct": o.is_correct,
                        "order_index": o.order_index,
                    }
                    for o in options
                ],
            }
        )
    return {
        "id": quiz.id,
        "title": quiz.title,
        "description": quiz.description,
        "passing_score": quiz.passing_score,
        "total_points": quiz.total_points,
        "module_id": quiz.module_id,
        "questions": q_list,
    }


def _assessment_payload(db: Session, assessment: Assessment) -> dict:
    rubric = (
        db.query(AssessmentRubric)
        .filter(AssessmentRubric.assessment_id == assessment.id)
        .order_by(AssessmentRubric.order_index.asc())
        .all()
    )
    return {
        "id": assessment.id,
        "assessment_type": assessment.assessment_type,
        "title": assessment.title,
        "description": assessment.description,
        "passing_score": assessment.passing_score,
        "module_id": assessment.module_id,
        "source_document_id": assessment.source_document_id,
        "source_section": assessment.source_section,
        "rubric": [
            {
                "id": r.id,
                "criterion": r.criterion,
                "weight": r.weight,
                "expected_performance": r.expected_performance,
                "pass_condition": r.pass_condition,
                "order_index": r.order_index,
            }
            for r in rubric
        ],
    }


def get_plan_detail(db: Session, plan_id: int) -> dict:
    plan = db.query(OnboardingPlan).filter(OnboardingPlan.id == plan_id).first()
    if plan is None:
        raise AppError("Plan not found", 404, "plan_not_found")

    employee = db.query(User).filter(User.id == plan.employee_user_id).first()
    role = db.query(JobRole).filter(JobRole.id == plan.job_role_id).first()

    stages = (
        db.query(PlanStage)
        .filter(PlanStage.plan_id == plan.id)
        .order_by(PlanStage.order_index.asc())
        .all()
    )
    modules = (
        db.query(LearningModule)
        .filter(LearningModule.plan_id == plan.id)
        .order_by(LearningModule.order_index.asc())
        .all()
    )
    checklists = (
        db.query(Checklist)
        .filter(Checklist.plan_id == plan.id)
        .order_by(Checklist.order_index.asc())
        .all()
    )
    tasks = (
        db.query(PlanTask)
        .filter(PlanTask.plan_id == plan.id)
        .order_by(PlanTask.order_index.asc())
        .all()
    )
    quizzes = db.query(Quiz).filter(Quiz.plan_id == plan.id).all()
    assessments = db.query(Assessment).filter(Assessment.plan_id == plan.id).all()

    run = None
    if plan.generation_run_id is not None:
        run = (
            db.query(GenerationRun)
            .filter(GenerationRun.id == plan.generation_run_id)
            .first()
        )

    return {
        "id": plan.id,
        "plan_code": plan.plan_code,
        "employee_user_id": plan.employee_user_id,
        "employee_name": employee.name if employee else None,
        "job_role_id": plan.job_role_id,
        "job_role_name": role.name if role else None,
        "status": plan.status,
        "notes": plan.notes,
        "summary_json": plan.summary_json,
        "created_at": plan.created_at,
        "updated_at": plan.updated_at,
        "stages": [
            {
                "id": s.id,
                "stage": s.stage,
                "order_index": s.order_index,
                "description": s.description,
            }
            for s in stages
        ],
        "modules": [_module_payload(db, m) for m in modules],
        "checklists": [_checklist_payload(db, c) for c in checklists],
        "tasks": [
            {
                "id": t.id,
                "task_code": t.task_code,
                "title": t.title,
                "description": t.description,
                "expected_outcome": t.expected_outcome,
                "completion_criteria": t.completion_criteria,
                "difficulty": t.difficulty,
                "due_stage": t.due_stage,
                "is_scenario": t.is_scenario,
                "requirement_id": t.requirement_id,
                "source_document_id": t.source_document_id,
                "source_section": t.source_section,
                "order_index": t.order_index,
            }
            for t in tasks
        ],
        "quizzes": [_quiz_payload(db, q) for q in quizzes],
        "assessments": [_assessment_payload(db, a) for a in assessments],
        "generation_run": {
            "id": run.id,
            "provider": run.provider,
            "model_name": run.model_name,
            "status": run.status,
            "parsed_ok": run.parsed_ok,
            "parse_error": run.parse_error,
            "retries": run.retries,
            "latency_ms": run.latency_ms,
            "token_estimate": run.token_estimate,
            "prompt_template_id": run.prompt_template_id,
            "prompt_version_id": run.prompt_version_id,
            "source_document_ids": run.source_document_ids,
            "input_summary": run.input_summary,
            "created_at": run.created_at,
            "finished_at": run.finished_at,
        }
        if run
        else None,
    }


def archive_plan(db: Session, plan_id: int) -> OnboardingPlan:
    plan = db.query(OnboardingPlan).filter(OnboardingPlan.id == plan_id).first()
    if plan is None:
        raise AppError("Plan not found", 404, "plan_not_found")
    plan.status = "archived"
    db.flush()
    return plan


def release_plan(db: Session, plan_id: int) -> OnboardingPlan:
    """Admin explicitly releases a validated plan to the employee. Only allowed
    when the plan has been validated at least once with an acceptable status."""
    from app.core.constants import PLAN_STATUS_RELEASABLE_FROM
    from app.models.validation import ValidationRun

    plan = db.query(OnboardingPlan).filter(OnboardingPlan.id == plan_id).first()
    if plan is None:
        raise AppError("Plan not found", 404, "plan_not_found")
    if plan.status in ("released", "in_progress", "completed"):
        raise AppError("Plan is already released", 409, "plan_already_released")
    if plan.status == "archived":
        raise AppError("Cannot release an archived plan", 409, "plan_archived")
    if plan.status not in PLAN_STATUS_RELEASABLE_FROM:
        raise AppError(
            f"Plan cannot be released from status '{plan.status}'. Validate it first.",
            409,
            "plan_not_releasable",
        )

    latest_run = (
        db.query(ValidationRun)
        .filter(ValidationRun.plan_id == plan_id)
        .order_by(ValidationRun.created_at.desc())
        .first()
    )
    if latest_run is None:
        raise AppError(
            "Plan must be validated before it can be released to the employee.",
            409,
            "validation_missing",
        )
    if latest_run.final_status in ("incomplete", "unsupported", "contradictory"):
        raise AppError(
            f"Plan's latest validation status is '{latest_run.final_status}'. "
            f"Regenerate or resolve findings before releasing.",
            409,
            "validation_blocking",
        )

    plan.status = "released"
    db.flush()
    return plan


def mark_started(db: Session, plan_id: int) -> None:
    """Called on first employee activity (module/task/quiz)."""
    plan = db.query(OnboardingPlan).filter(OnboardingPlan.id == plan_id).first()
    if plan is None:
        return
    if plan.status == "released":
        plan.status = "in_progress"
        db.flush()


def mark_completed_if_done(db: Session, plan_id: int) -> None:
    """When every mandatory module has a completion record and every assessment
    has an attempt, mark the plan completed."""
    from app.models.assessment import Assessment
    from app.models.attempt import AssessmentAttempt, QuizAttempt
    from app.models.learning_module import LearningModule
    from app.models.progress import ModuleCompletion
    from app.models.quiz import Quiz

    plan = db.query(OnboardingPlan).filter(OnboardingPlan.id == plan_id).first()
    if plan is None or plan.status not in ("in_progress", "released"):
        return

    mandatory_modules = (
        db.query(LearningModule.id)
        .filter(LearningModule.plan_id == plan_id, LearningModule.is_mandatory.is_(True))
        .all()
    )
    if not mandatory_modules:
        return
    mandatory_ids = {m.id for m in mandatory_modules}

    completed_ids = {
        c.module_id
        for c in db.query(ModuleCompletion)
        .filter(
            ModuleCompletion.module_id.in_(mandatory_ids),
            ModuleCompletion.employee_user_id == plan.employee_user_id,
            ModuleCompletion.status == "completed",
        )
        .all()
    }
    if completed_ids != mandatory_ids:
        return

    quiz_ids = [q.id for q in db.query(Quiz.id).filter(Quiz.plan_id == plan_id).all()]
    if quiz_ids:
        attempted_quiz_ids = {
            a.quiz_id
            for a in db.query(QuizAttempt)
            .filter(
                QuizAttempt.quiz_id.in_(quiz_ids),
                QuizAttempt.employee_user_id == plan.employee_user_id,
            )
            .all()
        }
        if set(quiz_ids) != attempted_quiz_ids:
            return

    assessment_ids = [
        a.id for a in db.query(Assessment.id).filter(Assessment.plan_id == plan_id).all()
    ]
    if assessment_ids:
        attempted_assessment_ids = {
            a.assessment_id
            for a in db.query(AssessmentAttempt)
            .filter(
                AssessmentAttempt.assessment_id.in_(assessment_ids),
                AssessmentAttempt.employee_user_id == plan.employee_user_id,
            )
            .all()
        }
        if set(assessment_ids) != attempted_assessment_ids:
            return

    plan.status = "completed"
    db.flush()
