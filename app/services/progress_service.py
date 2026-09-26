import json
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.assessment import Assessment, AssessmentRubric
from app.models.attempt import AssessmentAttempt, LearningRecommendation, QuizAttempt
from app.models.checklist import Checklist, ChecklistItem
from app.models.learning_module import LearningModule
from app.models.onboarding_plan import OnboardingPlan
from app.models.plan_task import PlanTask
from app.models.progress import (
    ChecklistItemCompletion,
    ModuleCompletion,
    TaskCompletion,
)
from app.models.quiz import Quiz, QuizOption, QuizQuestion
from app.models.user import User


WEAK_AREA_THRESHOLD = 60.0
PASS_THRESHOLD_DEFAULT = 70


def _get_plan(db: Session, plan_id: int) -> OnboardingPlan:
    plan = db.query(OnboardingPlan).filter(OnboardingPlan.id == plan_id).first()
    if plan is None:
        raise AppError("Plan not found", 404, "plan_not_found")
    return plan


def _get_employee(db: Session, user_id: int) -> User:
    u = db.query(User).filter(User.id == user_id).first()
    if u is None:
        raise AppError("Employee not found", 404, "employee_not_found")
    return u


def upsert_module_completion(
    db: Session, module_id: int, employee_user_id: int, status: str, notes: Optional[str]
) -> ModuleCompletion:
    module = db.query(LearningModule).filter(LearningModule.id == module_id).first()
    if module is None:
        raise AppError("Module not found", 404, "module_not_found")

    row = (
        db.query(ModuleCompletion)
        .filter(
            ModuleCompletion.module_id == module_id,
            ModuleCompletion.employee_user_id == employee_user_id,
        )
        .first()
    )
    now = datetime.utcnow()
    if row is None:
        row = ModuleCompletion(
            module_id=module_id,
            employee_user_id=employee_user_id,
            status=status,
            notes=notes,
            started_at=now if status != "not_started" else None,
            completed_at=now if status == "completed" else None,
        )
        db.add(row)
    else:
        row.status = status
        row.notes = notes if notes is not None else row.notes
        if status != "not_started" and row.started_at is None:
            row.started_at = now
        if status == "completed":
            row.completed_at = now
        elif status in ("in_progress", "not_started"):
            row.completed_at = None
    db.flush()
    return row


def upsert_task_completion(
    db: Session,
    task_id: int,
    employee_user_id: int,
    status: str,
    completion_notes: Optional[str],
    evidence_url: Optional[str],
) -> TaskCompletion:
    task = db.query(PlanTask).filter(PlanTask.id == task_id).first()
    if task is None:
        raise AppError("Task not found", 404, "task_not_found")

    row = (
        db.query(TaskCompletion)
        .filter(
            TaskCompletion.task_id == task_id,
            TaskCompletion.employee_user_id == employee_user_id,
        )
        .first()
    )
    now = datetime.utcnow()
    if row is None:
        row = TaskCompletion(
            task_id=task_id,
            employee_user_id=employee_user_id,
            status=status,
            completion_notes=completion_notes,
            evidence_url=evidence_url,
            started_at=now if status != "not_started" else None,
            completed_at=now if status == "completed" else None,
        )
        db.add(row)
    else:
        row.status = status
        if completion_notes is not None:
            row.completion_notes = completion_notes
        if evidence_url is not None:
            row.evidence_url = evidence_url
        if status != "not_started" and row.started_at is None:
            row.started_at = now
        if status == "completed":
            row.completed_at = now
        elif status in ("in_progress", "not_started"):
            row.completed_at = None
    db.flush()
    return row


def toggle_checklist_item(
    db: Session, item_id: int, employee_user_id: int, checked: bool
) -> ChecklistItemCompletion:
    item = db.query(ChecklistItem).filter(ChecklistItem.id == item_id).first()
    if item is None:
        raise AppError("Checklist item not found", 404, "checklist_item_not_found")

    row = (
        db.query(ChecklistItemCompletion)
        .filter(
            ChecklistItemCompletion.item_id == item_id,
            ChecklistItemCompletion.employee_user_id == employee_user_id,
        )
        .first()
    )
    now = datetime.utcnow()
    if row is None:
        row = ChecklistItemCompletion(
            item_id=item_id,
            employee_user_id=employee_user_id,
            checked=checked,
            completed_at=now if checked else None,
        )
        db.add(row)
    else:
        row.checked = checked
        row.completed_at = now if checked else None
    db.flush()
    return row


def _grade_question(
    question: QuizQuestion, options: List[QuizOption], picked_ids: List[int]
) -> Tuple[float, bool]:
    if not options:
        return 0.0, False

    correct_ids = {o.id for o in options if o.is_correct}
    picked_set = {o for o in picked_ids if o in {opt.id for opt in options}}

    if question.question_type in ("multiple_choice", "true_false"):
        got = picked_set == correct_ids and len(correct_ids) == 1
    elif question.question_type == "multiple_response":
        got = picked_set == correct_ids and len(correct_ids) > 0
    elif question.question_type == "scenario":
        got = picked_set == correct_ids and len(correct_ids) >= 1
    else:
        got = False

    return (float(question.points) if got else 0.0), got


def submit_quiz_attempt(
    db: Session,
    quiz_id: int,
    employee_user_id: int,
    answers: List[Dict],
) -> QuizAttempt:
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if quiz is None:
        raise AppError("Quiz not found", 404, "quiz_not_found")

    prior = (
        db.query(QuizAttempt)
        .filter(
            QuizAttempt.quiz_id == quiz_id,
            QuizAttempt.employee_user_id == employee_user_id,
        )
        .first()
    )
    if prior is not None:
        raise AppError(
            "You have already attempted this quiz; only one attempt is allowed.",
            409,
            "quiz_already_attempted",
        )

    questions = (
        db.query(QuizQuestion)
        .filter(QuizQuestion.quiz_id == quiz_id)
        .order_by(QuizQuestion.order_index.asc())
        .all()
    )
    if not questions:
        raise AppError("Quiz has no questions", 400, "quiz_empty")

    answer_map: Dict[int, List[int]] = {
        a["question_id"]: [int(x) for x in a.get("option_ids", [])] for a in answers
    }

    total_score = 0.0
    max_score = 0.0
    grading: List[Dict] = []

    for q in questions:
        options = (
            db.query(QuizOption)
            .filter(QuizOption.question_id == q.id)
            .order_by(QuizOption.order_index.asc())
            .all()
        )
        picked = answer_map.get(q.id, [])
        pts, correct = _grade_question(q, options, picked)
        max_score += float(q.points)
        total_score += pts
        grading.append(
            {
                "question_id": q.id,
                "picked": picked,
                "points_awarded": pts,
                "points_possible": q.points,
                "correct": correct,
                "explanation": q.explanation,
            }
        )

    percentage = (total_score / max_score * 100.0) if max_score > 0 else 0.0
    passed = percentage >= quiz.passing_score

    attempt = QuizAttempt(
        quiz_id=quiz_id,
        employee_user_id=employee_user_id,
        score=total_score,
        max_score=max_score,
        percentage=round(percentage, 2),
        passed=passed,
        answers_json=json.dumps([a.__dict__ if hasattr(a, "__dict__") else a for a in answers]),
        grading_json=json.dumps(grading),
    )
    db.add(attempt)
    db.flush()
    return attempt


def submit_assessment_attempt(
    db: Session,
    assessment_id: int,
    employee_user_id: int,
    rubric_scores: List[Dict],
    notes: Optional[str],
    graded_by: Optional[int],
) -> AssessmentAttempt:
    assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    if assessment is None:
        raise AppError("Assessment not found", 404, "assessment_not_found")

    prior = (
        db.query(AssessmentAttempt)
        .filter(
            AssessmentAttempt.assessment_id == assessment_id,
            AssessmentAttempt.employee_user_id == employee_user_id,
        )
        .first()
    )
    if prior is not None:
        raise AppError(
            "You have already submitted this assessment; only one submission is allowed.",
            409,
            "assessment_already_attempted",
        )

    rubrics = (
        db.query(AssessmentRubric)
        .filter(AssessmentRubric.assessment_id == assessment_id)
        .all()
    )
    if not rubrics:
        raise AppError("Assessment has no rubric", 400, "assessment_empty_rubric")

    rubric_map: Dict[int, AssessmentRubric] = {r.id: r for r in rubrics}
    score_map: Dict[int, float] = {}
    for entry in rubric_scores:
        rid = int(entry["rubric_id"])
        if rid not in rubric_map:
            raise AppError(
                f"Rubric row {rid} does not belong to this assessment",
                400,
                "invalid_rubric_row",
            )
        s = float(entry.get("score", 0.0))
        if s < 0.0 or s > 100.0:
            raise AppError(
                f"Rubric score for {rid} must be 0-100",
                400,
                "rubric_score_range",
            )
        score_map[rid] = s

    total_weighted = 0.0
    total_weight = 0.0
    for r in rubrics:
        awarded = score_map.get(r.id, 0.0)
        total_weighted += (awarded * r.weight)
        total_weight += r.weight

    percentage = (total_weighted / total_weight) if total_weight > 0 else 0.0
    percentage = round(percentage, 2)
    passed = percentage >= assessment.passing_score

    attempt = AssessmentAttempt(
        assessment_id=assessment_id,
        employee_user_id=employee_user_id,
        total_score=round(total_weighted, 2),
        max_score=round(total_weight * 100.0, 2),
        percentage=percentage,
        passed=passed,
        rubric_scores_json=json.dumps(rubric_scores),
        notes=notes,
        graded_by=graded_by,
    )
    db.add(attempt)
    db.flush()
    return attempt


def _list_modules(db: Session, plan_id: int) -> List[LearningModule]:
    return db.query(LearningModule).filter(LearningModule.plan_id == plan_id).all()


def _list_tasks(db: Session, plan_id: int) -> List[PlanTask]:
    return db.query(PlanTask).filter(PlanTask.plan_id == plan_id).all()


def _list_checklist_items(db: Session, plan_id: int) -> List[ChecklistItem]:
    checklists = db.query(Checklist).filter(Checklist.plan_id == plan_id).all()
    if not checklists:
        return []
    ids = [c.id for c in checklists]
    return db.query(ChecklistItem).filter(ChecklistItem.checklist_id.in_(ids)).all()


def _latest_quiz_attempts(
    db: Session, quiz_ids: List[int], employee_user_id: int
) -> Dict[int, QuizAttempt]:
    if not quiz_ids:
        return {}
    rows = (
        db.query(QuizAttempt)
        .filter(
            QuizAttempt.employee_user_id == employee_user_id,
            QuizAttempt.quiz_id.in_(quiz_ids),
        )
        .order_by(QuizAttempt.submitted_at.desc())
        .all()
    )
    out: Dict[int, QuizAttempt] = {}
    for r in rows:
        out.setdefault(r.quiz_id, r)
    return out


def _latest_assessment_attempts(
    db: Session, assessment_ids: List[int], employee_user_id: int
) -> Dict[int, AssessmentAttempt]:
    if not assessment_ids:
        return {}
    rows = (
        db.query(AssessmentAttempt)
        .filter(
            AssessmentAttempt.employee_user_id == employee_user_id,
            AssessmentAttempt.assessment_id.in_(assessment_ids),
        )
        .order_by(AssessmentAttempt.submitted_at.desc())
        .all()
    )
    out: Dict[int, AssessmentAttempt] = {}
    for r in rows:
        out.setdefault(r.assessment_id, r)
    return out


def _progress_assessment(
    plan: OnboardingPlan,
    employee: User,
    overall_pct: float,
    weak_count: int,
) -> str:
    if overall_pct >= 100.0:
        return "completed"

    days_since_join = None
    if employee.joining_date:
        today = date.today()
        days_since_join = (today - employee.joining_date).days

    expected_pct = 0.0
    if days_since_join is not None:
        if days_since_join <= 1:
            expected_pct = 10.0
        elif days_since_join <= 7:
            expected_pct = 20.0
        elif days_since_join <= 14:
            expected_pct = 35.0
        elif days_since_join <= 30:
            expected_pct = 55.0
        elif days_since_join <= 60:
            expected_pct = 80.0
        else:
            expected_pct = 100.0

    if weak_count >= 3:
        return "assessment_required"
    if days_since_join is None:
        return "on_track"
    if overall_pct >= expected_pct:
        return "on_track"
    if overall_pct >= expected_pct * 0.7:
        return "requires_attention"
    return "behind_schedule"


def compute_progress(
    db: Session, plan_id: int, employee_user_id: int
) -> Dict:
    plan = _get_plan(db, plan_id)
    employee = _get_employee(db, employee_user_id)

    modules = _list_modules(db, plan_id)
    tasks = _list_tasks(db, plan_id)
    checklist_items = _list_checklist_items(db, plan_id)
    quizzes = db.query(Quiz).filter(Quiz.plan_id == plan_id).all()
    assessments = db.query(Assessment).filter(Assessment.plan_id == plan_id).all()

    m_ids = [m.id for m in modules]
    t_ids = [t.id for t in tasks]
    ci_ids = [ci.id for ci in checklist_items]

    m_done = (
        db.query(ModuleCompletion)
        .filter(
            ModuleCompletion.employee_user_id == employee_user_id,
            ModuleCompletion.module_id.in_(m_ids) if m_ids else False,
            ModuleCompletion.status == "completed",
        )
        .count()
        if m_ids
        else 0
    )
    t_done = (
        db.query(TaskCompletion)
        .filter(
            TaskCompletion.employee_user_id == employee_user_id,
            TaskCompletion.task_id.in_(t_ids) if t_ids else False,
            TaskCompletion.status == "completed",
        )
        .count()
        if t_ids
        else 0
    )
    ci_done = (
        db.query(ChecklistItemCompletion)
        .filter(
            ChecklistItemCompletion.employee_user_id == employee_user_id,
            ChecklistItemCompletion.item_id.in_(ci_ids) if ci_ids else False,
            ChecklistItemCompletion.checked.is_(True),
        )
        .count()
        if ci_ids
        else 0
    )

    quiz_attempts = _latest_quiz_attempts(db, [q.id for q in quizzes], employee_user_id)
    assessment_attempts = _latest_assessment_attempts(
        db, [a.id for a in assessments], employee_user_id
    )

    def _pct(done: int, total: int) -> float:
        return round((done / total * 100.0), 2) if total > 0 else 0.0

    module_pct = _pct(m_done, len(modules))
    task_pct = _pct(t_done, len(tasks))
    checklist_pct = _pct(ci_done, len(checklist_items))

    quiz_scores = [a.percentage for a in quiz_attempts.values()]
    assessment_scores = [a.percentage for a in assessment_attempts.values()]

    quiz_avg = round(sum(quiz_scores) / len(quiz_scores), 2) if quiz_scores else None
    assessment_avg = (
        round(sum(assessment_scores) / len(assessment_scores), 2)
        if assessment_scores
        else None
    )

    overall_parts: List[float] = []
    if modules:
        overall_parts.append(module_pct)
    if tasks:
        overall_parts.append(task_pct)
    if checklist_items:
        overall_parts.append(checklist_pct)
    if quiz_scores:
        overall_parts.append(quiz_avg)
    if assessment_scores:
        overall_parts.append(assessment_avg)
    overall_pct = round(sum(overall_parts) / len(overall_parts), 2) if overall_parts else 0.0

    weak_areas: List[Dict] = []
    for quiz in quizzes:
        att = quiz_attempts.get(quiz.id)
        if att and att.percentage < WEAK_AREA_THRESHOLD:
            weak_areas.append(
                {
                    "kind": "quiz",
                    "id": quiz.id,
                    "title": quiz.title,
                    "percentage": att.percentage,
                    "module_id": quiz.module_id,
                }
            )
    for assessment in assessments:
        att = assessment_attempts.get(assessment.id)
        if att and att.percentage < WEAK_AREA_THRESHOLD:
            weak_areas.append(
                {
                    "kind": "assessment",
                    "id": assessment.id,
                    "title": assessment.title,
                    "percentage": att.percentage,
                    "module_id": assessment.module_id,
                }
            )

    progress_assessment = _progress_assessment(
        plan, employee, overall_pct, len(weak_areas)
    )

    return {
        "plan_id": plan_id,
        "employee_user_id": employee_user_id,
        "overall_percentage": overall_pct,
        "module_percentage": module_pct,
        "task_percentage": task_pct,
        "checklist_percentage": checklist_pct,
        "quiz_average": quiz_avg,
        "assessment_average": assessment_avg,
        "modules_completed": m_done,
        "modules_total": len(modules),
        "tasks_completed": t_done,
        "tasks_total": len(tasks),
        "checklist_items_completed": ci_done,
        "checklist_items_total": len(checklist_items),
        "quizzes_attempted": len(quiz_attempts),
        "quizzes_total": len(quizzes),
        "assessments_attempted": len(assessment_attempts),
        "assessments_total": len(assessments),
        "weak_areas": weak_areas,
        "progress_assessment": progress_assessment,
    }


def generate_recommendations(
    db: Session, plan_id: int, employee_user_id: int
) -> List[LearningRecommendation]:
    progress = compute_progress(db, plan_id, employee_user_id)
    plan = _get_plan(db, plan_id)

    created: List[LearningRecommendation] = []
    now = datetime.utcnow()

    for weak in progress["weak_areas"]:
        rec_type = (
            "revision_module" if weak["kind"] == "quiz" and weak.get("module_id") else "additional_quiz"
        )
        reason = (
            f"Weak performance ({weak['percentage']}%) on {weak['kind']} '{weak['title']}'"
        )
        priority = "high" if weak["percentage"] < 40.0 else "medium"

        exists = (
            db.query(LearningRecommendation)
            .filter(
                LearningRecommendation.plan_id == plan_id,
                LearningRecommendation.employee_user_id == employee_user_id,
                LearningRecommendation.recommendation_type == rec_type,
                LearningRecommendation.target_module_id == weak.get("module_id"),
                LearningRecommendation.status == "pending",
            )
            .first()
        )
        if exists:
            continue

        rec = LearningRecommendation(
            plan_id=plan_id,
            employee_user_id=employee_user_id,
            recommendation_type=rec_type,
            reason=reason,
            target_module_id=weak.get("module_id"),
            priority=priority,
            status="pending",
            score=weak["percentage"],
            created_at=now,
        )
        db.add(rec)
        db.flush()
        created.append(rec)

    if progress["overall_percentage"] >= 90.0 and progress["modules_total"] > 0:
        exists = (
            db.query(LearningRecommendation)
            .filter(
                LearningRecommendation.plan_id == plan_id,
                LearningRecommendation.employee_user_id == employee_user_id,
                LearningRecommendation.recommendation_type == "advanced_module",
                LearningRecommendation.status == "pending",
            )
            .first()
        )
        if not exists:
            rec = LearningRecommendation(
                plan_id=plan_id,
                employee_user_id=employee_user_id,
                recommendation_type="advanced_module",
                reason=(
                    f"Overall progress at {progress['overall_percentage']}% — "
                    f"employee is ready for advanced material"
                ),
                priority="low",
                status="pending",
                score=progress["overall_percentage"],
                created_at=now,
            )
            db.add(rec)
            db.flush()
            created.append(rec)

    if progress["progress_assessment"] == "behind_schedule":
        exists = (
            db.query(LearningRecommendation)
            .filter(
                LearningRecommendation.plan_id == plan_id,
                LearningRecommendation.employee_user_id == employee_user_id,
                LearningRecommendation.recommendation_type == "manager_review",
                LearningRecommendation.status == "pending",
            )
            .first()
        )
        if not exists:
            rec = LearningRecommendation(
                plan_id=plan_id,
                employee_user_id=employee_user_id,
                recommendation_type="manager_review",
                reason=(
                    f"Progress {progress['overall_percentage']}% is behind schedule; "
                    f"escalate to reporting manager"
                ),
                priority="high",
                status="pending",
                score=progress["overall_percentage"],
                created_at=now,
            )
            db.add(rec)
            db.flush()
            created.append(rec)

    return created


def list_recommendations(
    db: Session,
    plan_id: int,
    employee_user_id: Optional[int] = None,
    status: Optional[str] = None,
) -> List[LearningRecommendation]:
    q = db.query(LearningRecommendation).filter(
        LearningRecommendation.plan_id == plan_id
    )
    if employee_user_id is not None:
        q = q.filter(LearningRecommendation.employee_user_id == employee_user_id)
    if status:
        q = q.filter(LearningRecommendation.status == status)
    return q.order_by(LearningRecommendation.created_at.desc()).all()


def update_recommendation(
    db: Session, rec_id: int, status: str
) -> LearningRecommendation:
    rec = (
        db.query(LearningRecommendation)
        .filter(LearningRecommendation.id == rec_id)
        .first()
    )
    if rec is None:
        raise AppError("Recommendation not found", 404, "recommendation_not_found")
    rec.status = status
    if status in ("completed", "dismissed"):
        rec.resolved_at = datetime.utcnow()
    db.flush()
    return rec
