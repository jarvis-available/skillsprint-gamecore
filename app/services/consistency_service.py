import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.assessment import Assessment
from app.models.consistency import ConsistencyRun
from app.models.job_role import JobRole
from app.models.learning_module import LearningModule
from app.models.onboarding_plan import OnboardingPlan
from app.models.plan_task import PlanTask
from app.models.user import User
from app.services import generation_service


def _module_snapshot(db: Session, plan_id: int) -> Dict[int, Dict]:
    modules = (
        db.query(LearningModule)
        .filter(LearningModule.plan_id == plan_id)
        .order_by(LearningModule.order_index.asc())
        .all()
    )
    out: Dict[int, Dict] = {}
    for m in modules:
        key = m.requirement_id
        if key is None:
            continue
        out[key] = {
            "module_code": m.module_code,
            "title": m.title,
            "is_mandatory": m.is_mandatory,
            "source_document_id": m.source_document_id,
            "source_section": m.source_section,
        }
    return out


def _task_snapshot(db: Session, plan_id: int) -> Dict[int, Dict]:
    tasks = db.query(PlanTask).filter(PlanTask.plan_id == plan_id).all()
    out: Dict[int, Dict] = {}
    for t in tasks:
        if t.requirement_id is None:
            continue
        out[t.requirement_id] = {
            "task_code": t.task_code,
            "title": t.title,
            "source_document_id": t.source_document_id,
        }
    return out


def _assessment_topics(db: Session, plan_id: int) -> set:
    assessments = db.query(Assessment).filter(Assessment.plan_id == plan_id).all()
    return {(a.assessment_type, (a.title or "").strip().lower()) for a in assessments}


def _requirement_set(snapshot: Dict[int, Dict]) -> set:
    return set(snapshot.keys())


def _compare(
    db: Session, plan_a_id: int, plan_b_id: int
) -> Tuple[float, Dict]:
    modules_a = _module_snapshot(db, plan_a_id)
    modules_b = _module_snapshot(db, plan_b_id)
    tasks_a = _task_snapshot(db, plan_a_id)
    tasks_b = _task_snapshot(db, plan_b_id)

    covered_a = _requirement_set(modules_a) | _requirement_set(tasks_a)
    covered_b = _requirement_set(modules_b) | _requirement_set(tasks_b)

    intersection = covered_a & covered_b
    union = covered_a | covered_b
    matched_requirements = len(intersection)
    diverged_requirements = len(union) - matched_requirements

    matched_sources = 0
    matched_categories = 0
    for req_id in intersection:
        ma = modules_a.get(req_id)
        mb = modules_b.get(req_id)
        if ma and mb:
            if ma["source_document_id"] == mb["source_document_id"]:
                matched_sources += 1
            if ma["is_mandatory"] == mb["is_mandatory"]:
                matched_categories += 1
        else:
            ta = tasks_a.get(req_id)
            tb = tasks_b.get(req_id)
            if ta and tb and ta["source_document_id"] == tb["source_document_id"]:
                matched_sources += 1

    topics_a = _assessment_topics(db, plan_a_id)
    topics_b = _assessment_topics(db, plan_b_id)
    matched_topics = len(topics_a & topics_b)

    if len(union) == 0:
        req_score = 100.0
    else:
        req_score = (matched_requirements / len(union)) * 100.0
    if matched_requirements == 0:
        src_score = 100.0 if not diverged_requirements else 0.0
    else:
        src_score = (matched_sources / matched_requirements) * 100.0

    consistency_score = round((req_score * 0.6 + src_score * 0.4), 2)

    summary = {
        "req_score": round(req_score, 2),
        "source_score": round(src_score, 2),
        "matched_requirements": matched_requirements,
        "diverged_requirements": diverged_requirements,
        "matched_sources": matched_sources,
        "matched_module_categories": matched_categories,
        "matched_assessment_topics": matched_topics,
        "requirements_only_in_a": sorted(covered_a - covered_b),
        "requirements_only_in_b": sorted(covered_b - covered_a),
    }
    return consistency_score, summary


def run_consistency(
    db: Session,
    *,
    employee_user_id: int,
    job_role_id: int,
    max_chunks: int,
    triggered_by: Optional[int],
) -> ConsistencyRun:
    employee = db.query(User).filter(User.id == employee_user_id).first()
    if employee is None:
        raise AppError("Employee not found", 404, "employee_not_found")
    role = db.query(JobRole).filter(JobRole.id == job_role_id).first()
    if role is None:
        raise AppError("Job role not found", 404, "job_role_not_found")

    run = ConsistencyRun(
        employee_user_id=employee_user_id,
        job_role_id=job_role_id,
        status="running",
        triggered_by=triggered_by,
    )
    db.add(run)
    db.flush()
    db.commit()

    try:
        plan_a, _ = generation_service.generate_plan(
            db,
            employee_user_id=employee_user_id,
            job_role_id=job_role_id,
            max_chunks=max_chunks,
            triggered_by=triggered_by,
            plan_note="consistency_run_a",
        )
        plan_b, _ = generation_service.generate_plan(
            db,
            employee_user_id=employee_user_id,
            job_role_id=job_role_id,
            max_chunks=max_chunks,
            triggered_by=triggered_by,
            plan_note="consistency_run_b",
        )

        score, summary = _compare(db, plan_a.id, plan_b.id)

        run.plan_a_id = plan_a.id
        run.plan_b_id = plan_b.id
        run.consistency_score = score
        run.matched_requirements = summary["matched_requirements"]
        run.diverged_requirements = summary["diverged_requirements"]
        run.matched_sources = summary["matched_sources"]
        run.matched_module_categories = summary["matched_module_categories"]
        run.matched_assessment_topics = summary["matched_assessment_topics"]
        run.summary_json = json.dumps(summary)
        run.status = "succeeded"
    except Exception as exc:
        run.status = "failed"
        run.error_message = str(exc)[:2000]
    finally:
        run.finished_at = datetime.utcnow()
        db.commit()
        db.refresh(run)

    return run


def get_run(db: Session, run_id: int) -> ConsistencyRun:
    r = db.query(ConsistencyRun).filter(ConsistencyRun.id == run_id).first()
    if r is None:
        raise AppError("Consistency run not found", 404, "consistency_run_not_found")
    return r


def list_runs(db: Session, skip: int = 0, limit: int = 50) -> List[ConsistencyRun]:
    return (
        db.query(ConsistencyRun)
        .order_by(ConsistencyRun.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
