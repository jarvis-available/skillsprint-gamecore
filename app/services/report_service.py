from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.assessment import Assessment
from app.models.attempt import AssessmentAttempt, QuizAttempt
from app.models.document import Document
from app.models.job_role import JobRole
from app.models.learning_module import LearningModule
from app.models.onboarding_plan import OnboardingPlan
from app.models.plan_task import PlanTask
from app.models.quiz import Quiz
from app.models.requirement import Requirement
from app.models.role_requirement import RoleRequirement
from app.models.user import User
from app.models.validation import (
    RequirementComparison,
    ValidationFinding,
    ValidationRun,
)
from app.services import progress_service


REPORT_KINDS = (
    "employee_progress",
    "role_coverage",
    "mandatory_training",
    "assessment_results",
    "source_traceability",
    "hallucination_flags",
    "policy_coverage",
    "genai_python_comparison",
)


def _plan_lookup(db: Session, plan_ids: List[int]) -> Dict[int, OnboardingPlan]:
    if not plan_ids:
        return {}
    return {
        p.id: p
        for p in db.query(OnboardingPlan)
        .filter(OnboardingPlan.id.in_(plan_ids))
        .all()
    }


def employee_progress_report(
    db: Session, employee_user_id: Optional[int] = None
) -> List[Dict]:
    q = db.query(OnboardingPlan)
    if employee_user_id is not None:
        q = q.filter(OnboardingPlan.employee_user_id == employee_user_id)
    plans = q.all()

    rows: List[Dict] = []
    for p in plans:
        employee = db.query(User).filter(User.id == p.employee_user_id).first()
        role = db.query(JobRole).filter(JobRole.id == p.job_role_id).first()
        prog = progress_service.compute_progress(db, p.id, p.employee_user_id)
        rows.append(
            {
                "plan_id": p.id,
                "plan_code": p.plan_code,
                "employee_id": employee.employee_id if employee else "",
                "employee_name": employee.name if employee else "",
                "employee_email": employee.email if employee else "",
                "job_role": role.name if role else "",
                "plan_status": p.status,
                "overall_percentage": prog["overall_percentage"],
                "module_percentage": prog["module_percentage"],
                "task_percentage": prog["task_percentage"],
                "checklist_percentage": prog["checklist_percentage"],
                "quiz_average": prog["quiz_average"],
                "assessment_average": prog["assessment_average"],
                "progress_assessment": prog["progress_assessment"],
                "modules_completed": prog["modules_completed"],
                "modules_total": prog["modules_total"],
                "weak_areas": len(prog["weak_areas"]),
            }
        )
    return rows


def role_coverage_report(db: Session) -> List[Dict]:
    roles = db.query(JobRole).filter(JobRole.is_active.is_(True)).all()
    rows: List[Dict] = []
    for role in roles:
        links = (
            db.query(RoleRequirement, Requirement)
            .join(Requirement, RoleRequirement.requirement_id == Requirement.id)
            .filter(RoleRequirement.job_role_id == role.id)
            .all()
        )
        mandatory = [(l, r) for (l, r) in links if l.is_mandatory]
        optional = [(l, r) for (l, r) in links if not l.is_mandatory]
        rows.append(
            {
                "job_role_id": role.id,
                "job_role": role.name,
                "department": role.department or "",
                "total_requirements": len(links),
                "mandatory_requirements": len(mandatory),
                "optional_requirements": len(optional),
                "policy_reqs": sum(1 for _, r in links if r.requirement_type == "policy"),
                "process_reqs": sum(1 for _, r in links if r.requirement_type == "process"),
                "competency_reqs": sum(1 for _, r in links if r.requirement_type == "competency"),
                "assessment_reqs": sum(1 for _, r in links if r.requirement_type == "assessment"),
            }
        )
    return rows


def mandatory_training_report(db: Session) -> List[Dict]:
    plans = db.query(OnboardingPlan).all()
    rows: List[Dict] = []
    for p in plans:
        employee = db.query(User).filter(User.id == p.employee_user_id).first()
        role = db.query(JobRole).filter(JobRole.id == p.job_role_id).first()

        mandatory_modules = (
            db.query(LearningModule)
            .filter(
                LearningModule.plan_id == p.id,
                LearningModule.is_mandatory.is_(True),
            )
            .all()
        )
        mandatory_tasks = (
            db.query(PlanTask)
            .filter(
                PlanTask.plan_id == p.id,
                PlanTask.requirement_id.isnot(None),
            )
            .all()
        )

        rows.append(
            {
                "plan_code": p.plan_code,
                "employee_name": employee.name if employee else "",
                "role": role.name if role else "",
                "mandatory_module_count": len(mandatory_modules),
                "mandatory_task_count": len(mandatory_tasks),
                "plan_status": p.status,
            }
        )
    return rows


def assessment_results_report(db: Session) -> List[Dict]:
    attempts = db.query(AssessmentAttempt).all()
    rows: List[Dict] = []
    for a in attempts:
        assessment = db.query(Assessment).filter(Assessment.id == a.assessment_id).first()
        employee = db.query(User).filter(User.id == a.employee_user_id).first()
        rows.append(
            {
                "attempt_id": a.id,
                "assessment_id": a.assessment_id,
                "assessment_title": assessment.title if assessment else "",
                "assessment_type": assessment.assessment_type if assessment else "",
                "employee": employee.name if employee else "",
                "score": a.percentage,
                "passed": a.passed,
                "submitted_at": a.submitted_at.isoformat() if a.submitted_at else "",
            }
        )
    quiz_attempts = db.query(QuizAttempt).all()
    for qa in quiz_attempts:
        quiz = db.query(Quiz).filter(Quiz.id == qa.quiz_id).first()
        employee = db.query(User).filter(User.id == qa.employee_user_id).first()
        rows.append(
            {
                "attempt_id": qa.id,
                "assessment_id": qa.quiz_id,
                "assessment_title": quiz.title if quiz else "",
                "assessment_type": "quiz",
                "employee": employee.name if employee else "",
                "score": qa.percentage,
                "passed": qa.passed,
                "submitted_at": qa.submitted_at.isoformat() if qa.submitted_at else "",
            }
        )
    return rows


def source_traceability_report(db: Session) -> List[Dict]:
    modules = db.query(LearningModule).all()
    rows: List[Dict] = []
    for m in modules:
        doc = None
        if m.source_document_id:
            doc = db.query(Document).filter(Document.id == m.source_document_id).first()
        rows.append(
            {
                "kind": "module",
                "id": m.id,
                "code": m.module_code,
                "title": m.title,
                "source_document_code": doc.doc_code if doc else "",
                "source_document_name": doc.name if doc else "",
                "source_section": m.source_section or "",
                "source_chunk_ids": m.source_chunk_ids or "",
                "is_active_source": bool(doc and doc.is_active),
                "is_superseded": bool(doc and doc.superseded_by_id is not None),
            }
        )
    tasks = db.query(PlanTask).all()
    for t in tasks:
        doc = None
        if t.source_document_id:
            doc = db.query(Document).filter(Document.id == t.source_document_id).first()
        rows.append(
            {
                "kind": "task",
                "id": t.id,
                "code": t.task_code,
                "title": t.title,
                "source_document_code": doc.doc_code if doc else "",
                "source_document_name": doc.name if doc else "",
                "source_section": t.source_section or "",
                "source_chunk_ids": "",
                "is_active_source": bool(doc and doc.is_active),
                "is_superseded": bool(doc and doc.superseded_by_id is not None),
            }
        )
    return rows


def hallucination_flags_report(db: Session) -> List[Dict]:
    findings = (
        db.query(ValidationFinding)
        .filter(ValidationFinding.issue_type == "hallucination")
        .all()
    )
    rows: List[Dict] = []
    for f in findings:
        rows.append(
            {
                "finding_id": f.id,
                "validation_run_id": f.validation_run_id,
                "entity_type": f.entity_type,
                "entity_code": f.entity_code or "",
                "severity": f.severity,
                "cosine_score": f.score,
                "source_reference": f.source_reference or "",
                "message": f.message,
                "created_at": f.created_at.isoformat() if f.created_at else "",
            }
        )
    return rows


def policy_coverage_report(db: Session) -> List[Dict]:
    runs = db.query(ValidationRun).all()
    rows: List[Dict] = []
    for r in runs:
        plan = db.query(OnboardingPlan).filter(OnboardingPlan.id == r.plan_id).first()
        rows.append(
            {
                "validation_run_id": r.id,
                "plan_code": plan.plan_code if plan else "",
                "coverage_score": r.coverage_score,
                "traceability_score": r.traceability_score,
                "mandatory_total": r.mandatory_total,
                "mandatory_covered": r.mandatory_covered,
                "missing": r.missing_requirement_count,
                "unsupported": r.unsupported_requirement_count,
                "duplicates": r.duplicate_count,
                "contradictions": r.contradiction_count,
                "hallucinations": r.hallucination_count,
                "final_status": r.final_status or "",
                "created_at": r.created_at.isoformat() if r.created_at else "",
            }
        )
    return rows


def genai_python_comparison_report(db: Session) -> List[Dict]:
    rows = db.query(RequirementComparison).all()
    out: List[Dict] = []
    for c in rows:
        req = db.query(Requirement).filter(Requirement.id == c.requirement_id).first()
        run = (
            db.query(ValidationRun)
            .filter(ValidationRun.id == c.validation_run_id)
            .first()
        )
        plan = (
            db.query(OnboardingPlan)
            .filter(OnboardingPlan.id == run.plan_id)
            .first()
            if run
            else None
        )
        out.append(
            {
                "comparison_id": c.id,
                "plan_code": plan.plan_code if plan else "",
                "requirement_code": req.req_code if req else "",
                "requirement_title": req.title if req else "",
                "coverage_status": c.coverage_status,
                "traceability_status": c.traceability_status,
                "validation_status": c.validation_status,
                "matched": c.matched,
                "match_details": c.match_details or "",
            }
        )
    return out


def build_report(db: Session, kind: str, **kwargs) -> List[Dict]:
    if kind not in REPORT_KINDS:
        raise AppError(f"Unknown report kind: {kind}", 400, "unknown_report_kind")
    if kind == "employee_progress":
        return employee_progress_report(db, kwargs.get("employee_user_id"))
    if kind == "role_coverage":
        return role_coverage_report(db)
    if kind == "mandatory_training":
        return mandatory_training_report(db)
    if kind == "assessment_results":
        return assessment_results_report(db)
    if kind == "source_traceability":
        return source_traceability_report(db)
    if kind == "hallucination_flags":
        return hallucination_flags_report(db)
    if kind == "policy_coverage":
        return policy_coverage_report(db)
    if kind == "genai_python_comparison":
        return genai_python_comparison_report(db)
    return []
