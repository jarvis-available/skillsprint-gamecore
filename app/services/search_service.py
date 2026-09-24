from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.assessment import Assessment
from app.models.document import Document
from app.models.job_role import JobRole
from app.models.learning_module import LearningModule
from app.models.onboarding_plan import OnboardingPlan
from app.models.plan_task import PlanTask
from app.models.quiz import Quiz
from app.models.requirement import Requirement
from app.models.user import User


def _hit(kind: str, item_id: int, label: str, extra: Optional[Dict] = None) -> Dict:
    out = {"kind": kind, "id": item_id, "label": label}
    if extra:
        out.update(extra)
    return out


def cross_entity(
    db: Session,
    query: str,
    kinds: Optional[List[str]] = None,
    limit: int = 20,
) -> Dict[str, List[Dict]]:
    if not query or len(query.strip()) < 2:
        return {}
    like = f"%{query.strip()}%"

    results: Dict[str, List[Dict]] = {}

    def _want(kind: str) -> bool:
        return kinds is None or kind in kinds

    if _want("user"):
        rows = (
            db.query(User)
            .filter(
                (User.name.ilike(like))
                | (User.email.ilike(like))
                | (User.employee_id.ilike(like))
            )
            .limit(limit)
            .all()
        )
        results["user"] = [
            _hit(
                "user",
                u.id,
                f"{u.name} ({u.employee_id})",
                {"email": u.email, "system_role": u.system_role, "department": u.department},
            )
            for u in rows
        ]

    if _want("job_role"):
        rows = (
            db.query(JobRole)
            .filter(
                (JobRole.name.ilike(like)) | (JobRole.department.ilike(like))
            )
            .limit(limit)
            .all()
        )
        results["job_role"] = [
            _hit("job_role", r.id, r.name, {"department": r.department})
            for r in rows
        ]

    if _want("document"):
        rows = (
            db.query(Document)
            .filter(
                (Document.name.ilike(like))
                | (Document.doc_code.ilike(like))
                | (Document.description.ilike(like))
            )
            .limit(limit)
            .all()
        )
        results["document"] = [
            _hit(
                "document",
                d.id,
                f"{d.doc_code} — {d.name}",
                {"doc_type": d.doc_type, "department": d.department},
            )
            for d in rows
        ]

    if _want("requirement"):
        rows = (
            db.query(Requirement)
            .filter(
                (Requirement.title.ilike(like))
                | (Requirement.req_code.ilike(like))
                | (Requirement.competency.ilike(like))
            )
            .limit(limit)
            .all()
        )
        results["requirement"] = [
            _hit(
                "requirement",
                r.id,
                f"{r.req_code} — {r.title}",
                {"must_type": r.must_type, "requirement_type": r.requirement_type},
            )
            for r in rows
        ]

    if _want("module"):
        rows = (
            db.query(LearningModule)
            .filter(
                (LearningModule.title.ilike(like))
                | (LearningModule.module_code.ilike(like))
                | (LearningModule.purpose.ilike(like))
            )
            .limit(limit)
            .all()
        )
        results["module"] = [
            _hit(
                "module",
                m.id,
                f"{m.module_code}: {m.title}",
                {"plan_id": m.plan_id, "is_mandatory": m.is_mandatory},
            )
            for m in rows
        ]

    if _want("task"):
        rows = (
            db.query(PlanTask)
            .filter(
                (PlanTask.title.ilike(like))
                | (PlanTask.task_code.ilike(like))
                | (PlanTask.description.ilike(like))
            )
            .limit(limit)
            .all()
        )
        results["task"] = [
            _hit(
                "task",
                t.id,
                f"{t.task_code}: {t.title}",
                {"plan_id": t.plan_id, "difficulty": t.difficulty},
            )
            for t in rows
        ]

    if _want("plan"):
        rows = (
            db.query(OnboardingPlan)
            .filter(
                (OnboardingPlan.plan_code.ilike(like))
                | (OnboardingPlan.notes.ilike(like))
            )
            .limit(limit)
            .all()
        )
        results["plan"] = [
            _hit(
                "plan",
                p.id,
                p.plan_code,
                {"status": p.status, "employee_user_id": p.employee_user_id},
            )
            for p in rows
        ]

    if _want("quiz"):
        rows = (
            db.query(Quiz)
            .filter((Quiz.title.ilike(like)) | (Quiz.description.ilike(like)))
            .limit(limit)
            .all()
        )
        results["quiz"] = [
            _hit(
                "quiz",
                q.id,
                q.title,
                {"plan_id": q.plan_id, "passing_score": q.passing_score},
            )
            for q in rows
        ]

    if _want("assessment"):
        rows = (
            db.query(Assessment)
            .filter(
                (Assessment.title.ilike(like)) | (Assessment.description.ilike(like))
            )
            .limit(limit)
            .all()
        )
        results["assessment"] = [
            _hit(
                "assessment",
                a.id,
                a.title,
                {"plan_id": a.plan_id, "assessment_type": a.assessment_type},
            )
            for a in rows
        ]

    return results
