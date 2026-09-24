import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core import ai_client
from app.core.exceptions import AppError
from app.models.assessment import Assessment, AssessmentRubric
from app.models.checklist import Checklist, ChecklistItem
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.document_version import DocumentVersion
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
from app.models.requirement import Requirement
from app.models.role_requirement import RoleRequirement
from app.models.user import User
from app.schemas.ai_output import AIOnboardingPlan
from app.services import prompt_service


MAX_CHUNK_CHARS = 1200


def _gather_matrix(db: Session, job_role_id: int) -> List[dict]:
    rows = (
        db.query(RoleRequirement, Requirement)
        .join(Requirement, RoleRequirement.requirement_id == Requirement.id)
        .filter(
            RoleRequirement.job_role_id == job_role_id,
            Requirement.is_active.is_(True),
        )
        .order_by(Requirement.req_code.asc())
        .all()
    )
    out: List[dict] = []
    for link, req in rows:
        out.append(
            {
                "requirement_id": req.id,
                "req_code": req.req_code,
                "title": req.title,
                "requirement_type": req.requirement_type,
                "must_type": req.must_type,
                "is_mandatory": link.is_mandatory,
                "priority": link.priority_override or req.priority,
                "due_stage": link.due_stage_override or req.due_stage,
                "competency": req.competency,
                "assessment_topic": req.assessment_topic,
                "source_document_id": req.source_document_id,
                "source_section": req.source_section,
            }
        )
    return out


def _relevant_document_ids(matrix: List[dict], role_department: Optional[str], db: Session) -> List[int]:
    ids = {row["source_document_id"] for row in matrix if row.get("source_document_id")}

    if role_department:
        dept_docs = (
            db.query(Document.id)
            .filter(
                Document.is_active.is_(True),
                Document.department == role_department,
            )
            .all()
        )
        for (doc_id,) in dept_docs:
            ids.add(doc_id)

    return list(ids)


def _current_version_map(db: Session, document_ids: List[int]) -> Dict[int, DocumentVersion]:
    if not document_ids:
        return {}
    versions = (
        db.query(DocumentVersion)
        .filter(
            DocumentVersion.document_id.in_(document_ids),
            DocumentVersion.is_current.is_(True),
        )
        .all()
    )
    return {v.document_id: v for v in versions}


def _pick_chunks(
    db: Session,
    version_ids: List[int],
    matrix: List[dict],
    max_chunks: int,
) -> List[DocumentChunk]:
    if not version_ids:
        return []

    preferred_sections = {
        (row["source_document_id"], row["source_section"])
        for row in matrix
        if row.get("source_document_id") and row.get("source_section")
    }

    q = db.query(DocumentChunk).filter(
        DocumentChunk.version_id.in_(version_ids),
        (DocumentChunk.adversarial_flags.is_(None))
        | (DocumentChunk.adversarial_flags == ""),
    )

    all_chunks = q.order_by(
        DocumentChunk.document_id.asc(), DocumentChunk.order_index.asc()
    ).all()

    ranked: List[Tuple[int, DocumentChunk]] = []
    for chunk in all_chunks:
        score = 0
        key = (chunk.document_id, chunk.section_number)
        if key in preferred_sections:
            score += 100
        if chunk.section_number:
            score += 10
        if chunk.heading:
            score += 5
        ranked.append((score, chunk))

    ranked.sort(key=lambda t: (-t[0], t[1].document_id, t[1].order_index))
    return [c for _, c in ranked[:max_chunks]]


def _build_source_context(
    chunks: List[DocumentChunk],
    version_map: Dict[int, DocumentVersion],
    documents: Dict[int, Document],
) -> str:
    if not chunks:
        return "(no source content available)"

    parts: List[str] = []
    current_doc_id = None
    for chunk in chunks:
        if chunk.document_id != current_doc_id:
            doc = documents.get(chunk.document_id)
            version = version_map.get(chunk.document_id)
            if doc:
                parts.append(
                    f"\n=== DOCUMENT #{doc.id} ({doc.doc_code} \"{doc.name}\") — version {version.version_label if version else 'unknown'} ===\n"
                )
            current_doc_id = chunk.document_id

        heading = f' "{chunk.heading}"' if chunk.heading else ""
        section = f" §{chunk.section_number}" if chunk.section_number else ""
        page = f" (page {chunk.page_number})" if chunk.page_number else ""
        content = chunk.content or ""
        if len(content) > MAX_CHUNK_CHARS:
            content = content[:MAX_CHUNK_CHARS] + "..."
        parts.append(f"\n--- CHUNK #{chunk.id}{section}{heading}{page} ---\n")
        parts.append(prompt_service.sanitize_source_text(content))
        parts.append("\n")
    return "".join(parts)


def _next_plan_code(db: Session, employee: User) -> str:
    ts = int(time.time())
    return f"PLAN-{employee.employee_id}-{ts}"


def _persist_plan(
    db: Session,
    plan: OnboardingPlan,
    ai: AIOnboardingPlan,
) -> None:
    stage_map: Dict[str, int] = {}
    for idx, stage in enumerate(ai.stages):
        row = PlanStage(
            plan_id=plan.id,
            stage=stage.stage,
            order_index=idx,
            description=stage.description,
        )
        db.add(row)
        db.flush()
        stage_map[stage.stage] = row.id

    module_map: Dict[str, int] = {}
    for idx, module in enumerate(ai.modules):
        chunk_ids_str = (
            ",".join(str(cid) for cid in module.source_chunk_ids)
            if module.source_chunk_ids
            else None
        )
        row = LearningModule(
            plan_id=plan.id,
            stage_id=stage_map.get(module.stage) if module.stage else None,
            requirement_id=module.requirement_id,
            module_code=module.module_code,
            title=module.title,
            purpose=module.purpose,
            key_concepts=module.key_concepts,
            estimated_minutes=module.estimated_minutes,
            completion_criteria=module.completion_criteria,
            source_document_id=module.source_document_id,
            source_section=module.source_section,
            source_chunk_ids=chunk_ids_str,
            is_mandatory=module.is_mandatory,
            order_index=idx,
        )
        db.add(row)
        db.flush()
        module_map[module.module_code] = row.id

        for oi, text in enumerate(module.objectives):
            db.add(
                LearningObjective(
                    module_id=row.id, text=text, order_index=oi
                )
            )
        for ai_idx, description in enumerate(module.activities):
            db.add(
                ModuleActivity(
                    module_id=row.id,
                    description=description,
                    order_index=ai_idx,
                )
            )
    db.flush()

    for idx, checklist in enumerate(ai.checklists):
        row = Checklist(
            plan_id=plan.id,
            stage_id=stage_map.get(checklist.stage) if checklist.stage else None,
            title=checklist.title,
            description=checklist.description,
            order_index=idx,
        )
        db.add(row)
        db.flush()
        for ii, item in enumerate(checklist.items):
            db.add(
                ChecklistItem(
                    checklist_id=row.id,
                    activity=item.activity,
                    is_required=item.is_required,
                    due_stage=item.due_stage,
                    source_document_id=item.source_document_id,
                    source_section=item.source_section,
                    responsible_role=item.responsible_role,
                    order_index=ii,
                )
            )

    for idx, task in enumerate(ai.tasks):
        db.add(
            PlanTask(
                plan_id=plan.id,
                stage_id=stage_map.get(task.due_stage) if task.due_stage else None,
                requirement_id=task.requirement_id,
                task_code=task.task_code,
                title=task.title,
                description=task.description,
                expected_outcome=task.expected_outcome,
                completion_criteria=task.completion_criteria,
                difficulty=task.difficulty,
                due_stage=task.due_stage,
                source_document_id=task.source_document_id,
                source_section=task.source_section,
                is_scenario=task.is_scenario,
                order_index=idx,
            )
        )

    for quiz in ai.quizzes:
        total_points = sum(q.points for q in quiz.questions)
        quiz_row = Quiz(
            plan_id=plan.id,
            module_id=module_map.get(quiz.module_code) if quiz.module_code else None,
            title=quiz.title,
            description=quiz.description,
            passing_score=quiz.passing_score,
            total_points=total_points,
        )
        db.add(quiz_row)
        db.flush()

        for qi, question in enumerate(quiz.questions):
            correct = [i for i, opt in enumerate(question.options) if opt.is_correct]
            question_row = QuizQuestion(
                quiz_id=quiz_row.id,
                question_type=question.question_type,
                prompt_text=question.prompt_text,
                difficulty=question.difficulty,
                source_document_id=question.source_document_id,
                source_section=question.source_section,
                explanation=question.explanation,
                correct_answer_json=json.dumps(correct),
                points=question.points,
                order_index=qi,
            )
            db.add(question_row)
            db.flush()

            for oi, option in enumerate(question.options):
                db.add(
                    QuizOption(
                        question_id=question_row.id,
                        text=option.text,
                        is_correct=option.is_correct,
                        order_index=oi,
                    )
                )

    for assessment in ai.assessments:
        row = Assessment(
            plan_id=plan.id,
            module_id=module_map.get(assessment.module_code)
            if assessment.module_code
            else None,
            assessment_type=assessment.assessment_type,
            title=assessment.title,
            description=assessment.description,
            passing_score=assessment.passing_score,
            source_document_id=assessment.source_document_id,
            source_section=assessment.source_section,
        )
        db.add(row)
        db.flush()
        for ri, rubric in enumerate(assessment.rubric):
            db.add(
                AssessmentRubric(
                    assessment_id=row.id,
                    criterion=rubric.criterion,
                    weight=rubric.weight,
                    expected_performance=rubric.expected_performance,
                    pass_condition=rubric.pass_condition,
                    order_index=ri,
                )
            )


def _summary(ai: AIOnboardingPlan) -> dict:
    return {
        "stage_count": len(ai.stages),
        "module_count": len(ai.modules),
        "mandatory_module_count": sum(1 for m in ai.modules if m.is_mandatory),
        "checklist_count": len(ai.checklists),
        "task_count": len(ai.tasks),
        "quiz_count": len(ai.quizzes),
        "quiz_question_count": sum(len(q.questions) for q in ai.quizzes),
        "assessment_count": len(ai.assessments),
        "summary_text": ai.plan_summary,
        "notes": ai.notes,
    }


def generate_plan(
    db: Session,
    *,
    employee_user_id: int,
    job_role_id: int,
    max_chunks: int,
    triggered_by: Optional[int],
    plan_note: Optional[str] = None,
) -> Tuple[OnboardingPlan, GenerationRun]:
    employee = db.query(User).filter(User.id == employee_user_id).first()
    if employee is None:
        raise AppError("Employee not found", 404, "employee_not_found")

    job_role = db.query(JobRole).filter(JobRole.id == job_role_id).first()
    if job_role is None:
        raise AppError("Job role not found", 404, "job_role_not_found")

    matrix = _gather_matrix(db, job_role_id)
    if not matrix:
        raise AppError(
            "Role has no assigned requirements; build the matrix first",
            400,
            "empty_role_matrix",
        )

    doc_ids = _relevant_document_ids(matrix, job_role.department, db)
    documents = {
        d.id: d
        for d in db.query(Document).filter(Document.id.in_(doc_ids)).all()
    } if doc_ids else {}
    version_map = _current_version_map(db, doc_ids)
    version_ids = [v.id for v in version_map.values()]
    chunks = _pick_chunks(db, version_ids, matrix, max_chunks)

    source_versions_snapshot = {
        str(doc_id): {
            "doc_code": documents[doc_id].doc_code,
            "version": v.version_label,
            "version_number": v.version_number,
            "sha256": v.sha256,
        }
        for doc_id, v in version_map.items()
        if doc_id in documents
    }

    template, prompt_version = prompt_service.get_active_version(db, "onboarding_plan")
    variables = {
        "employee_name": employee.name,
        "employee_id": employee.employee_id,
        "job_role_name": job_role.name,
        "department": job_role.department or "unspecified",
        "experience_level": employee.experience_level or "unspecified",
        "joining_date": employee.joining_date.isoformat() if employee.joining_date else "unspecified",
        "requirement_matrix_json": json.dumps(matrix, indent=2),
        "source_context": _build_source_context(chunks, version_map, documents),
    }
    prompt_text = prompt_service.render_prompt(prompt_version.content, variables)

    plan = OnboardingPlan(
        plan_code=_next_plan_code(db, employee),
        employee_user_id=employee.id,
        job_role_id=job_role.id,
        status="generating",
        notes=plan_note,
        created_by=triggered_by,
    )
    db.add(plan)
    db.flush()

    run = GenerationRun(
        plan_id=plan.id,
        prompt_template_id=template.id,
        prompt_version_id=prompt_version.id,
        prompt_snapshot=prompt_text,
        provider="pending",
        model_name=prompt_version.model_hint or "unknown",
        input_summary=(
            f"employee_id={employee.employee_id}, role={job_role.name}, "
            f"matrix_size={len(matrix)}, docs={len(documents)}, chunks={len(chunks)}"
        ),
        source_document_ids=",".join(str(d) for d in doc_ids),
        source_versions_json=json.dumps(source_versions_snapshot),
        status="running",
        triggered_by=triggered_by,
    )
    db.add(run)
    db.flush()
    db.commit()

    try:
        provider_result = ai_client.generate_json(
            prompt_text,
            temperature=prompt_version.temperature_hint or 0.2,
        )
    except ai_client.AIError as exc:
        run.status = "failed"
        run.parse_error = str(exc)[:2000]
        run.finished_at = datetime.utcnow()
        plan.status = "manual_review"
        db.commit()
        raise AppError(f"AI generation failed: {exc}", 502, "generation_failed")

    result = provider_result.result
    run.output_raw = result.text
    run.provider = provider_result.provider
    run.model_name = result.model
    run.latency_ms = result.latency_ms
    run.retries = result.retries
    run.token_estimate = result.token_estimate
    if provider_result.fallback_used:
        run.input_summary = (run.input_summary or "") + " | fallback_used=true"

    try:
        parsed = ai_client.parse_json_output(provider_result.provider, result.text)
    except Exception as exc:
        run.status = "invalid_json"
        run.parse_error = str(exc)[:2000]
        run.finished_at = datetime.utcnow()
        plan.status = "manual_review"
        db.commit()
        raise AppError(f"Invalid JSON from {provider_result.provider}: {exc}", 502, "invalid_json")

    run.output_parsed_json = json.dumps(parsed)

    try:
        ai_plan = AIOnboardingPlan.model_validate(parsed)
    except ValidationError as exc:
        run.status = "schema_mismatch"
        run.parse_error = str(exc)[:2000]
        run.finished_at = datetime.utcnow()
        plan.status = "manual_review"
        db.commit()
        raise AppError(
            "AI output failed schema validation", 502, "schema_mismatch"
        )

    _persist_plan(db, plan, ai_plan)

    plan.summary_json = json.dumps(_summary(ai_plan))
    plan.status = "ready"
    plan.generation_run_id = run.id
    run.status = "succeeded"
    run.parsed_ok = True
    run.finished_at = datetime.utcnow()

    db.commit()
    db.refresh(plan)
    db.refresh(run)
    return plan, run
