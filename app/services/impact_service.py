import json
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.assessment import Assessment
from app.models.checklist import Checklist, ChecklistItem
from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.models.learning_module import LearningModule
from app.models.onboarding_plan import OnboardingPlan
from app.models.plan_task import PlanTask
from app.models.policy_impact import PolicyImpact
from app.models.quiz import Quiz, QuizQuestion


def analyze_document_impact(
    db: Session, document_id: int, triggered_by: Optional[int]
) -> PolicyImpact:
    document = db.query(Document).filter(Document.id == document_id).first()
    if document is None:
        raise AppError("Document not found", 404, "document_not_found")

    versions = (
        db.query(DocumentVersion)
        .filter(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.version_number.desc())
        .all()
    )
    to_version = next((v for v in versions if v.is_current), None)
    from_version = next(
        (v for v in versions if not v.is_current), None
    )

    module_ids = [
        m.id
        for m in db.query(LearningModule)
        .filter(LearningModule.source_document_id == document_id)
        .all()
    ]
    task_ids = [
        t.id
        for t in db.query(PlanTask)
        .filter(PlanTask.source_document_id == document_id)
        .all()
    ]
    checklist_item_ids = [
        ci.id
        for ci in db.query(ChecklistItem)
        .filter(ChecklistItem.source_document_id == document_id)
        .all()
    ]
    quiz_question_ids = [
        q.id
        for q in db.query(QuizQuestion)
        .filter(QuizQuestion.source_document_id == document_id)
        .all()
    ]
    assessment_ids = [
        a.id
        for a in db.query(Assessment)
        .filter(Assessment.source_document_id == document_id)
        .all()
    ]

    plan_id_set: set[int] = set()
    if module_ids:
        for row in db.query(LearningModule.plan_id).filter(LearningModule.id.in_(module_ids)).all():
            plan_id_set.add(row[0])
    if task_ids:
        for row in db.query(PlanTask.plan_id).filter(PlanTask.id.in_(task_ids)).all():
            plan_id_set.add(row[0])
    if checklist_item_ids:
        checklist_ids = [
            row[0]
            for row in db.query(ChecklistItem.checklist_id)
            .filter(ChecklistItem.id.in_(checklist_item_ids))
            .all()
        ]
        if checklist_ids:
            for row in (
                db.query(Checklist.plan_id).filter(Checklist.id.in_(checklist_ids)).all()
            ):
                plan_id_set.add(row[0])
    if quiz_question_ids:
        quiz_ids = [
            row[0]
            for row in db.query(QuizQuestion.quiz_id)
            .filter(QuizQuestion.id.in_(quiz_question_ids))
            .all()
        ]
        if quiz_ids:
            for row in db.query(Quiz.plan_id).filter(Quiz.id.in_(quiz_ids)).all():
                plan_id_set.add(row[0])
    if assessment_ids:
        for row in (
            db.query(Assessment.plan_id).filter(Assessment.id.in_(assessment_ids)).all()
        ):
            plan_id_set.add(row[0])

    employee_ids: List[int] = []
    if plan_id_set:
        employee_ids = [
            row[0]
            for row in db.query(OnboardingPlan.employee_user_id)
            .filter(OnboardingPlan.id.in_(list(plan_id_set)))
            .all()
        ]

    summary = {
        "document_id": document_id,
        "doc_code": document.doc_code,
        "doc_name": document.name,
        "from_version_id": from_version.id if from_version else None,
        "from_version_label": from_version.version_label if from_version else None,
        "to_version_id": to_version.id if to_version else None,
        "to_version_label": to_version.version_label if to_version else None,
        "affected_plan_count": len(plan_id_set),
        "affected_module_count": len(module_ids),
        "affected_task_count": len(task_ids),
        "affected_quiz_question_count": len(quiz_question_ids),
        "affected_assessment_count": len(assessment_ids),
        "affected_employee_count": len(set(employee_ids)),
    }

    impact = PolicyImpact(
        document_id=document_id,
        from_version_id=from_version.id if from_version else None,
        to_version_id=to_version.id if to_version else None,
        status="analyzed",
        affected_plan_ids=",".join(str(x) for x in sorted(plan_id_set)) or None,
        affected_module_ids=",".join(str(x) for x in sorted(module_ids)) or None,
        affected_task_ids=",".join(str(x) for x in sorted(task_ids)) or None,
        affected_quiz_question_ids=",".join(str(x) for x in sorted(quiz_question_ids)) or None,
        affected_assessment_ids=",".join(str(x) for x in sorted(assessment_ids)) or None,
        affected_employee_user_ids=",".join(str(x) for x in sorted(set(employee_ids))) or None,
        summary_json=json.dumps(summary),
        triggered_by=triggered_by,
    )
    db.add(impact)
    db.flush()
    return impact


def get_impact(db: Session, impact_id: int) -> PolicyImpact:
    row = db.query(PolicyImpact).filter(PolicyImpact.id == impact_id).first()
    if row is None:
        raise AppError("Impact analysis not found", 404, "impact_not_found")
    return row


def list_impacts(
    db: Session, document_id: Optional[int] = None, skip: int = 0, limit: int = 50
) -> List[PolicyImpact]:
    q = db.query(PolicyImpact)
    if document_id is not None:
        q = q.filter(PolicyImpact.document_id == document_id)
    return q.order_by(PolicyImpact.created_at.desc()).offset(skip).limit(limit).all()


def parse_plan_ids(impact: PolicyImpact) -> List[int]:
    if not impact.affected_plan_ids:
        return []
    return [int(x) for x in impact.affected_plan_ids.split(",") if x.strip().isdigit()]


def mark_regenerated(db: Session, impact_id: int) -> PolicyImpact:
    row = get_impact(db, impact_id)
    row.status = "regenerated"
    db.flush()
    return row


def mark_dismissed(db: Session, impact_id: int) -> PolicyImpact:
    row = get_impact(db, impact_id)
    row.status = "dismissed"
    db.flush()
    return row
