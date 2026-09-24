import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Tuple

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.assessment import Assessment, AssessmentRubric
from app.models.checklist import Checklist, ChecklistItem
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.document_version import DocumentVersion
from app.models.job_role import JobRole
from app.models.learning_module import (
    LearningModule,
    LearningObjective,
    ModuleActivity,
)
from app.models.onboarding_plan import OnboardingPlan
from app.models.plan_task import PlanTask
from app.models.precedence_rule import PrecedenceRule
from app.models.quiz import Quiz, QuizOption, QuizQuestion
from app.models.requirement import Requirement
from app.models.requirement_prerequisite import RequirementPrerequisite
from app.models.role_requirement import RoleRequirement
from app.models.user import User
from app.models.validation import (
    RequirementComparison,
    ValidationFinding,
    ValidationRun,
)
from app.services import similarity_service


HALLUCINATION_MIN_COS = 0.15
DUPLICATE_THRESHOLD = 0.85
ROLE_RELEVANCE_MIN = 0.10
DISTRACTOR_CONFLICT_MARGIN = 0.10


@dataclass
class _Finding:
    entity_type: str
    entity_id: Optional[int]
    entity_code: Optional[str]
    issue_type: str
    severity: str
    message: str
    expected: Optional[str] = None
    actual: Optional[str] = None
    source_reference: Optional[str] = None
    score: Optional[float] = None


@dataclass
class _CheckState:
    findings: List[_Finding] = field(default_factory=list)
    mandatory_total: int = 0
    mandatory_covered: int = 0
    optional_total: int = 0
    optional_covered: int = 0
    missing_requirement_count: int = 0
    unsupported_requirement_count: int = 0
    duplicate_count: int = 0
    contradiction_count: int = 0
    hallucination_count: int = 0
    role_irrelevance_count: int = 0
    sequence_violation_count: int = 0
    distractor_conflict_count: int = 0
    outdated_source_count: int = 0
    coverage_score: float = 0.0
    traceability_score: float = 0.0
    requirement_consistency_score: float = 0.0


def _get_plan(db: Session, plan_id: int) -> OnboardingPlan:
    plan = db.query(OnboardingPlan).filter(OnboardingPlan.id == plan_id).first()
    if plan is None:
        raise AppError("Plan not found", 404, "plan_not_found")
    return plan


def _matrix_rows(db: Session, job_role_id: int) -> List[Tuple[RoleRequirement, Requirement]]:
    return (
        db.query(RoleRequirement, Requirement)
        .join(Requirement, RoleRequirement.requirement_id == Requirement.id)
        .filter(RoleRequirement.job_role_id == job_role_id)
        .all()
    )


def _plan_modules(db: Session, plan_id: int) -> List[LearningModule]:
    return (
        db.query(LearningModule)
        .filter(LearningModule.plan_id == plan_id)
        .order_by(LearningModule.order_index.asc())
        .all()
    )


def _plan_tasks(db: Session, plan_id: int) -> List[PlanTask]:
    return db.query(PlanTask).filter(PlanTask.plan_id == plan_id).all()


def _plan_checklists(db: Session, plan_id: int) -> List[Checklist]:
    return db.query(Checklist).filter(Checklist.plan_id == plan_id).all()


def _plan_quizzes(db: Session, plan_id: int) -> List[Quiz]:
    return db.query(Quiz).filter(Quiz.plan_id == plan_id).all()


def _plan_assessments(db: Session, plan_id: int) -> List[Assessment]:
    return db.query(Assessment).filter(Assessment.plan_id == plan_id).all()


def _chunks_by_ids(db: Session, ids: Sequence[int]) -> Dict[int, DocumentChunk]:
    if not ids:
        return {}
    rows = db.query(DocumentChunk).filter(DocumentChunk.id.in_(list(ids))).all()
    return {c.id: c for c in rows}


def _chunks_by_doc_section(
    db: Session, doc_ids: Sequence[int]
) -> Dict[Tuple[int, Optional[str]], List[DocumentChunk]]:
    if not doc_ids:
        return {}
    rows = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id.in_(list(doc_ids)))
        .all()
    )
    out: Dict[Tuple[int, Optional[str]], List[DocumentChunk]] = {}
    for c in rows:
        out.setdefault((c.document_id, c.section_number), []).append(c)
    return out


def _parse_chunk_ids(raw: Optional[str]) -> List[int]:
    if not raw:
        return []
    out: List[int] = []
    for token in raw.split(","):
        token = token.strip()
        if token.isdigit():
            out.append(int(token))
    return out


def _precedence_map(db: Session) -> Dict[str, int]:
    rows = db.query(PrecedenceRule).filter(PrecedenceRule.is_active.is_(True)).all()
    return {r.source_type: r.rank for r in rows}


def _resolve_chunk_content(
    db: Session,
    document_id: Optional[int],
    section: Optional[str],
    chunk_ids: Sequence[int],
    chunk_lookup: Dict[int, DocumentChunk],
    section_lookup: Dict[Tuple[int, Optional[str]], List[DocumentChunk]],
) -> str:
    pieces: List[str] = []
    for cid in chunk_ids:
        chunk = chunk_lookup.get(cid)
        if chunk is not None:
            pieces.append(chunk.content or "")
    if not pieces and document_id and section:
        chunks = section_lookup.get((document_id, section), [])
        pieces.extend((c.content or "") for c in chunks)
    return "\n\n".join(pieces).strip()


def _check_coverage_and_comparisons(
    db: Session,
    plan: OnboardingPlan,
    matrix: List[Tuple[RoleRequirement, Requirement]],
    modules: List[LearningModule],
    tasks: List[PlanTask],
    state: _CheckState,
    run_id: int,
) -> None:
    mandatory_by_requirement: Dict[int, List[str]] = {}
    for module in modules:
        if module.requirement_id is not None:
            mandatory_by_requirement.setdefault(module.requirement_id, []).append(
                f"module:{module.module_code}"
            )
    for task in tasks:
        if task.requirement_id is not None:
            mandatory_by_requirement.setdefault(task.requirement_id, []).append(
                f"task:{task.task_code}"
            )

    for link, req in matrix:
        covered_by = mandatory_by_requirement.get(req.id, [])
        is_mandatory = link.is_mandatory
        if is_mandatory:
            state.mandatory_total += 1
        else:
            state.optional_total += 1

        coverage_status = "covered" if covered_by else "missing"
        traceability_status = (
            "traced" if req.source_document_id is not None else "missing"
        )

        if covered_by:
            if is_mandatory:
                state.mandatory_covered += 1
            else:
                state.optional_covered += 1
            validation_status = "verified"
        else:
            if is_mandatory:
                state.missing_requirement_count += 1
                validation_status = "requirement_missing"
                state.findings.append(
                    _Finding(
                        entity_type="requirement",
                        entity_id=req.id,
                        entity_code=req.req_code,
                        issue_type="coverage_missing",
                        severity="error",
                        message=f"Mandatory requirement {req.req_code} ({req.title}) not covered by any module or task",
                    )
                )
            else:
                validation_status = "verified_with_warning"

        db.add(
            RequirementComparison(
                validation_run_id=run_id,
                requirement_id=req.id,
                python_expected_json=json.dumps(
                    {
                        "req_code": req.req_code,
                        "title": req.title,
                        "must_type": req.must_type,
                        "is_mandatory": is_mandatory,
                        "priority": link.priority_override or req.priority,
                        "due_stage": link.due_stage_override or req.due_stage,
                        "source_document_id": req.source_document_id,
                        "source_section": req.source_section,
                    }
                ),
                genai_result_json=json.dumps({"covered_by": covered_by}),
                coverage_status=coverage_status,
                traceability_status=traceability_status,
                validation_status=validation_status,
                matched=bool(covered_by),
                match_details=", ".join(covered_by) if covered_by else "not covered",
            )
        )

    known_requirement_ids = {req.id for _, req in matrix}
    for module in modules:
        if module.requirement_id and module.requirement_id not in known_requirement_ids:
            state.unsupported_requirement_count += 1
            state.findings.append(
                _Finding(
                    entity_type="module",
                    entity_id=module.id,
                    entity_code=module.module_code,
                    issue_type="requirement_unsupported",
                    severity="warning",
                    message=(
                        f"Module {module.module_code} references requirement {module.requirement_id} "
                        f"which is not in the role's matrix"
                    ),
                )
            )
    for task in tasks:
        if task.requirement_id and task.requirement_id not in known_requirement_ids:
            state.unsupported_requirement_count += 1
            state.findings.append(
                _Finding(
                    entity_type="task",
                    entity_id=task.id,
                    entity_code=task.task_code,
                    issue_type="requirement_unsupported",
                    severity="warning",
                    message=(
                        f"Task {task.task_code} references requirement {task.requirement_id} "
                        f"which is not in the role's matrix"
                    ),
                )
            )

    if state.mandatory_total > 0:
        state.coverage_score = (state.mandatory_covered / state.mandatory_total) * 100.0
    else:
        state.coverage_score = 100.0


def _check_traceability(
    db: Session,
    state: _CheckState,
    modules: List[LearningModule],
    tasks: List[PlanTask],
    checklists: List[Checklist],
    quizzes: List[Quiz],
    assessments: List[Assessment],
    document_lookup: Dict[int, Document],
    version_lookup: Dict[int, DocumentVersion],
    chunk_lookup: Dict[int, DocumentChunk],
) -> None:
    checked = 0
    traced = 0

    def _check_item(entity_type: str, entity_id: int, entity_code: Optional[str], doc_id, section, chunk_ids):
        nonlocal checked, traced
        checked += 1
        if not doc_id:
            state.findings.append(
                _Finding(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    entity_code=entity_code,
                    issue_type="source_missing",
                    severity="warning",
                    message=f"{entity_type} {entity_code or entity_id} has no source_document_id",
                )
            )
            return

        doc = document_lookup.get(doc_id)
        if doc is None:
            state.findings.append(
                _Finding(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    entity_code=entity_code,
                    issue_type="source_invalid",
                    severity="error",
                    message=f"{entity_type} {entity_code or entity_id} cites document #{doc_id} which does not exist",
                )
            )
            return

        if not doc.is_active or doc.superseded_by_id is not None:
            state.outdated_source_count += 1
            state.findings.append(
                _Finding(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    entity_code=entity_code,
                    issue_type="outdated_source",
                    severity="warning",
                    message=(
                        f"{entity_type} {entity_code or entity_id} cites {doc.doc_code} "
                        f"which is inactive or superseded"
                    ),
                    source_reference=f"doc#{doc_id}",
                )
            )
            return

        for cid in chunk_ids:
            chunk = chunk_lookup.get(cid)
            if chunk is None or chunk.document_id != doc_id:
                state.findings.append(
                    _Finding(
                        entity_type=entity_type,
                        entity_id=entity_id,
                        entity_code=entity_code,
                        issue_type="source_invalid",
                        severity="warning",
                        message=(
                            f"{entity_type} {entity_code or entity_id} cites chunk #{cid} "
                            f"not belonging to doc #{doc_id}"
                        ),
                    )
                )
                return

        traced += 1

    for m in modules:
        _check_item(
            "module", m.id, m.module_code, m.source_document_id, m.source_section, _parse_chunk_ids(m.source_chunk_ids)
        )
    for t in tasks:
        _check_item("task", t.id, t.task_code, t.source_document_id, t.source_section, [])
    for cl in checklists:
        items = db.query(ChecklistItem).filter(ChecklistItem.checklist_id == cl.id).all()
        for item in items:
            _check_item(
                "checklist_item", item.id, None, item.source_document_id, item.source_section, []
            )
    for q in quizzes:
        questions = db.query(QuizQuestion).filter(QuizQuestion.quiz_id == q.id).all()
        for qu in questions:
            _check_item("quiz_question", qu.id, None, qu.source_document_id, qu.source_section, [])
    for a in assessments:
        _check_item(
            "assessment", a.id, None, a.source_document_id, a.source_section, []
        )

    if checked == 0:
        state.traceability_score = 100.0
    else:
        state.traceability_score = (traced / checked) * 100.0


def _check_hallucinations(
    db: Session,
    state: _CheckState,
    modules: List[LearningModule],
    tasks: List[PlanTask],
    quizzes: List[Quiz],
    document_lookup: Dict[int, Document],
    chunk_lookup: Dict[int, DocumentChunk],
    section_lookup: Dict[Tuple[int, Optional[str]], List[DocumentChunk]],
) -> None:
    def _score_text(entity_type, entity_id, entity_code, text, doc_id, section, chunk_ids):
        if not text or not doc_id:
            return
        source = _resolve_chunk_content(
            db, doc_id, section, chunk_ids, chunk_lookup, section_lookup
        )
        if not source:
            return
        score = similarity_service.cosine_scores(text, [source])[0]
        if score < HALLUCINATION_MIN_COS:
            state.hallucination_count += 1
            state.findings.append(
                _Finding(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    entity_code=entity_code,
                    issue_type="hallucination",
                    severity="warning",
                    message=(
                        f"{entity_type} {entity_code or entity_id}: content shows low overlap "
                        f"({score:.2f}) with cited source"
                    ),
                    score=float(score),
                    source_reference=f"doc#{doc_id} §{section}" if section else f"doc#{doc_id}",
                )
            )

    for m in modules:
        combined = " ".join(
            filter(None, [m.title, m.purpose, m.key_concepts, m.completion_criteria])
        )
        _score_text(
            "module",
            m.id,
            m.module_code,
            combined,
            m.source_document_id,
            m.source_section,
            _parse_chunk_ids(m.source_chunk_ids),
        )
    for t in tasks:
        combined = " ".join(
            filter(
                None,
                [t.title, t.description, t.expected_outcome, t.completion_criteria],
            )
        )
        _score_text(
            "task",
            t.id,
            t.task_code,
            combined,
            t.source_document_id,
            t.source_section,
            [],
        )
    for quiz in quizzes:
        questions = db.query(QuizQuestion).filter(QuizQuestion.quiz_id == quiz.id).all()
        for qu in questions:
            _score_text(
                "quiz_question",
                qu.id,
                None,
                qu.prompt_text,
                qu.source_document_id,
                qu.source_section,
                [],
            )


def _check_duplicates(
    db: Session,
    state: _CheckState,
    modules: List[LearningModule],
    tasks: List[PlanTask],
    quizzes: List[Quiz],
    checklists: List[Checklist],
) -> None:
    def _flag(entity_type, items, text_fn):
        texts = [text_fn(x) for x in items]
        pairs = similarity_service.duplicates(texts, threshold=DUPLICATE_THRESHOLD)
        for i, j, score in pairs:
            state.duplicate_count += 1
            state.findings.append(
                _Finding(
                    entity_type=entity_type,
                    entity_id=items[j].id,
                    entity_code=str(getattr(items[j], "module_code", None) or getattr(items[j], "task_code", None) or items[j].id),
                    issue_type="duplicate",
                    severity="warning",
                    message=(
                        f"Duplicate {entity_type} detected: item #{items[i].id} and #{items[j].id} "
                        f"cosine={score:.2f}"
                    ),
                    score=float(score),
                )
            )

    _flag("module", modules, lambda m: f"{m.title} {m.purpose or ''}")
    _flag("task", tasks, lambda t: f"{t.title} {t.description or ''}")

    for quiz in quizzes:
        questions = db.query(QuizQuestion).filter(QuizQuestion.quiz_id == quiz.id).all()
        _flag("quiz_question", questions, lambda qu: qu.prompt_text)

    for cl in checklists:
        items = db.query(ChecklistItem).filter(ChecklistItem.checklist_id == cl.id).all()
        _flag("checklist_item", items, lambda ci: ci.activity)


def _check_contradictions(
    db: Session,
    state: _CheckState,
    modules: List[LearningModule],
    tasks: List[PlanTask],
    document_lookup: Dict[int, Document],
    precedence: Dict[str, int],
) -> None:
    for m in modules:
        if m.source_document_id and document_lookup.get(m.source_document_id):
            doc = document_lookup[m.source_document_id]
            if doc.superseded_by_id is not None:
                state.contradiction_count += 1
                state.findings.append(
                    _Finding(
                        entity_type="module",
                        entity_id=m.id,
                        entity_code=m.module_code,
                        issue_type="contradiction",
                        severity="warning",
                        message=(
                            f"Module {m.module_code} cites {doc.doc_code} which has been superseded "
                            f"by document #{doc.superseded_by_id}"
                        ),
                    )
                )

    grouped_by_req: Dict[int, List[LearningModule]] = {}
    for m in modules:
        if m.requirement_id is not None:
            grouped_by_req.setdefault(m.requirement_id, []).append(m)

    for req_id, mods in grouped_by_req.items():
        if len(mods) < 2:
            continue
        for i in range(len(mods)):
            for j in range(i + 1, len(mods)):
                a = mods[i]
                b = mods[j]
                text_a = f"{a.title} {a.purpose or ''} {a.completion_criteria or ''}"
                text_b = f"{b.title} {b.purpose or ''} {b.completion_criteria or ''}"
                if (
                    similarity_service.has_negation(text_a)
                    != similarity_service.has_negation(text_b)
                    and similarity_service.keyword_overlap(text_a, text_b) > 0.3
                ):
                    state.contradiction_count += 1
                    state.findings.append(
                        _Finding(
                            entity_type="module",
                            entity_id=b.id,
                            entity_code=b.module_code,
                            issue_type="contradiction",
                            severity="warning",
                            message=(
                                f"Modules {a.module_code} and {b.module_code} share requirement "
                                f"#{req_id} but differ on negation phrasing"
                            ),
                        )
                    )


def _check_role_relevance(
    db: Session,
    state: _CheckState,
    role: JobRole,
    matrix: List[Tuple[RoleRequirement, Requirement]],
    modules: List[LearningModule],
    tasks: List[PlanTask],
) -> None:
    role_corpus_parts = [role.name or "", role.department or "", role.description or ""]
    role_corpus_parts.extend(req.title for _, req in matrix)
    role_corpus_parts.extend(req.competency or "" for _, req in matrix)
    role_context = " ".join(p for p in role_corpus_parts if p).strip()
    if not role_context:
        return

    for m in modules:
        text = f"{m.title} {m.purpose or ''} {m.key_concepts or ''}"
        score = similarity_service.cosine_scores(text, [role_context])[0]
        if score < ROLE_RELEVANCE_MIN:
            state.role_irrelevance_count += 1
            state.findings.append(
                _Finding(
                    entity_type="module",
                    entity_id=m.id,
                    entity_code=m.module_code,
                    issue_type="role_irrelevance",
                    severity="info",
                    message=(
                        f"Module {m.module_code} may be off-topic for role {role.name} "
                        f"(cosine={score:.2f})"
                    ),
                    score=float(score),
                )
            )
    for t in tasks:
        text = f"{t.title} {t.description or ''}"
        score = similarity_service.cosine_scores(text, [role_context])[0]
        if score < ROLE_RELEVANCE_MIN:
            state.role_irrelevance_count += 1
            state.findings.append(
                _Finding(
                    entity_type="task",
                    entity_id=t.id,
                    entity_code=t.task_code,
                    issue_type="role_irrelevance",
                    severity="info",
                    message=(
                        f"Task {t.task_code} may be off-topic for role {role.name} "
                        f"(cosine={score:.2f})"
                    ),
                    score=float(score),
                )
            )


def _check_sequence(
    db: Session,
    state: _CheckState,
    modules: List[LearningModule],
) -> None:
    order: Dict[int, int] = {
        m.requirement_id: m.order_index
        for m in modules
        if m.requirement_id is not None
    }
    if not order:
        return

    prereq_rows = (
        db.query(RequirementPrerequisite)
        .filter(RequirementPrerequisite.requirement_id.in_(list(order.keys())))
        .all()
    )
    for row in prereq_rows:
        req_idx = order.get(row.requirement_id)
        prereq_idx = order.get(row.prerequisite_id)
        if req_idx is None or prereq_idx is None:
            continue
        if prereq_idx >= req_idx:
            state.sequence_violation_count += 1
            state.findings.append(
                _Finding(
                    entity_type="module",
                    entity_id=None,
                    entity_code=None,
                    issue_type="sequence_violation",
                    severity="warning",
                    message=(
                        f"Prerequisite requirement #{row.prerequisite_id} appears at or after "
                        f"dependent requirement #{row.requirement_id} in module order"
                    ),
                )
            )


def _check_distractors(
    db: Session,
    state: _CheckState,
    quizzes: List[Quiz],
    chunk_lookup: Dict[int, DocumentChunk],
    section_lookup: Dict[Tuple[int, Optional[str]], List[DocumentChunk]],
) -> None:
    for quiz in quizzes:
        questions = db.query(QuizQuestion).filter(QuizQuestion.quiz_id == quiz.id).all()
        for qu in questions:
            source = _resolve_chunk_content(
                db,
                qu.source_document_id,
                qu.source_section,
                [],
                chunk_lookup,
                section_lookup,
            )
            if not source:
                continue
            options = (
                db.query(QuizOption)
                .filter(QuizOption.question_id == qu.id)
                .order_by(QuizOption.order_index.asc())
                .all()
            )
            if not options:
                continue
            correct_texts = [o.text for o in options if o.is_correct]
            if not correct_texts:
                continue

            texts = [o.text for o in options]
            scores = similarity_service.cosine_scores(source, texts)
            best_idx = int(max(range(len(scores)), key=lambda i: scores[i]))
            best_score = scores[best_idx]
            if not options[best_idx].is_correct:
                correct_max = max(
                    (scores[i] for i, o in enumerate(options) if o.is_correct),
                    default=0.0,
                )
                if best_score - correct_max > DISTRACTOR_CONFLICT_MARGIN:
                    state.distractor_conflict_count += 1
                    state.findings.append(
                        _Finding(
                            entity_type="quiz_question",
                            entity_id=qu.id,
                            entity_code=None,
                            issue_type="distractor_conflict",
                            severity="warning",
                            message=(
                                f"Distractor '{options[best_idx].text[:60]}' aligns with source "
                                f"more closely than the marked correct answer"
                            ),
                            score=float(best_score),
                        )
                    )


def _derive_final_status(state: _CheckState) -> str:
    if state.missing_requirement_count > 0:
        return "requirement_missing"
    if state.contradiction_count > 0:
        return "contradiction_detected"
    if state.outdated_source_count > 0:
        return "outdated_source"
    if state.hallucination_count > 0:
        return "source_support_missing"
    if state.unsupported_requirement_count > 0:
        return "unsupported_requirement"
    if state.duplicate_count > 0 or state.sequence_violation_count > 0 or state.distractor_conflict_count > 0:
        return "verified_with_warning"
    if state.role_irrelevance_count > 0:
        return "verified_with_warning"
    if state.coverage_score >= 100.0 and state.traceability_score >= 100.0:
        return "verified"
    if state.coverage_score >= 100.0:
        return "verified_with_warning"
    return "partially_verified"


def validate_plan(
    db: Session, plan_id: int, triggered_by: Optional[int]
) -> ValidationRun:
    plan = _get_plan(db, plan_id)

    run = ValidationRun(
        plan_id=plan.id,
        status="running",
        triggered_by=triggered_by,
    )
    db.add(run)
    db.flush()
    db.commit()

    state = _CheckState()

    try:
        role = db.query(JobRole).filter(JobRole.id == plan.job_role_id).first()
        matrix = _matrix_rows(db, plan.job_role_id)
        modules = _plan_modules(db, plan.id)
        tasks = _plan_tasks(db, plan.id)
        checklists = _plan_checklists(db, plan.id)
        quizzes = _plan_quizzes(db, plan.id)
        assessments = _plan_assessments(db, plan.id)

        doc_ids: set[int] = set()
        for m in modules:
            if m.source_document_id:
                doc_ids.add(m.source_document_id)
        for t in tasks:
            if t.source_document_id:
                doc_ids.add(t.source_document_id)
        for cl in checklists:
            items = db.query(ChecklistItem).filter(ChecklistItem.checklist_id == cl.id).all()
            for item in items:
                if item.source_document_id:
                    doc_ids.add(item.source_document_id)
        for quiz in quizzes:
            questions = db.query(QuizQuestion).filter(QuizQuestion.quiz_id == quiz.id).all()
            for qu in questions:
                if qu.source_document_id:
                    doc_ids.add(qu.source_document_id)
        for a in assessments:
            if a.source_document_id:
                doc_ids.add(a.source_document_id)
        for _, req in matrix:
            if req.source_document_id:
                doc_ids.add(req.source_document_id)

        document_lookup = {
            d.id: d for d in db.query(Document).filter(Document.id.in_(list(doc_ids))).all()
        }
        version_lookup = {
            v.document_id: v
            for v in db.query(DocumentVersion)
            .filter(
                DocumentVersion.document_id.in_(list(doc_ids)),
                DocumentVersion.is_current.is_(True),
            )
            .all()
        }
        chunk_ids: set[int] = set()
        for m in modules:
            chunk_ids.update(_parse_chunk_ids(m.source_chunk_ids))
        chunk_lookup = _chunks_by_ids(db, list(chunk_ids))
        section_lookup = _chunks_by_doc_section(db, list(doc_ids))

        precedence = _precedence_map(db)

        _check_coverage_and_comparisons(
            db, plan, matrix, modules, tasks, state, run.id
        )
        _check_traceability(
            db,
            state,
            modules,
            tasks,
            checklists,
            quizzes,
            assessments,
            document_lookup,
            version_lookup,
            chunk_lookup,
        )
        _check_hallucinations(
            db,
            state,
            modules,
            tasks,
            quizzes,
            document_lookup,
            chunk_lookup,
            section_lookup,
        )
        _check_duplicates(db, state, modules, tasks, quizzes, checklists)
        _check_contradictions(db, state, modules, tasks, document_lookup, precedence)
        if role is not None:
            _check_role_relevance(db, state, role, matrix, modules, tasks)
        _check_sequence(db, state, modules)
        _check_distractors(db, state, quizzes, chunk_lookup, section_lookup)

        for f in state.findings:
            db.add(
                ValidationFinding(
                    validation_run_id=run.id,
                    entity_type=f.entity_type,
                    entity_id=f.entity_id,
                    entity_code=f.entity_code,
                    issue_type=f.issue_type,
                    severity=f.severity,
                    message=f.message,
                    expected=f.expected,
                    actual=f.actual,
                    source_reference=f.source_reference,
                    score=f.score,
                )
            )

        run.coverage_score = state.coverage_score
        run.traceability_score = state.traceability_score
        run.requirement_consistency_score = state.requirement_consistency_score
        run.mandatory_total = state.mandatory_total
        run.mandatory_covered = state.mandatory_covered
        run.optional_total = state.optional_total
        run.optional_covered = state.optional_covered
        run.missing_requirement_count = state.missing_requirement_count
        run.unsupported_requirement_count = state.unsupported_requirement_count
        run.duplicate_count = state.duplicate_count
        run.contradiction_count = state.contradiction_count
        run.hallucination_count = state.hallucination_count
        run.role_irrelevance_count = state.role_irrelevance_count
        run.sequence_violation_count = state.sequence_violation_count
        run.distractor_conflict_count = state.distractor_conflict_count
        run.outdated_source_count = state.outdated_source_count
        run.final_status = _derive_final_status(state)
        run.status = "succeeded"
        run.summary_json = json.dumps(
            {
                "coverage_score": round(state.coverage_score, 2),
                "traceability_score": round(state.traceability_score, 2),
                "mandatory_total": state.mandatory_total,
                "mandatory_covered": state.mandatory_covered,
                "findings": len(state.findings),
                "final_status": run.final_status,
            }
        )

        plan.status = run.final_status
    except Exception as exc:
        run.status = "failed"
        run.error_message = str(exc)[:2000]
    finally:
        run.finished_at = datetime.utcnow()
        db.commit()
        db.refresh(run)

    return run


def get_run(db: Session, run_id: int) -> ValidationRun:
    run = db.query(ValidationRun).filter(ValidationRun.id == run_id).first()
    if run is None:
        raise AppError("Validation run not found", 404, "validation_run_not_found")
    return run


def list_findings(db: Session, run_id: int) -> List[ValidationFinding]:
    return (
        db.query(ValidationFinding)
        .filter(ValidationFinding.validation_run_id == run_id)
        .order_by(ValidationFinding.severity.desc(), ValidationFinding.id.asc())
        .all()
    )


def list_comparisons(db: Session, run_id: int) -> List[RequirementComparison]:
    return (
        db.query(RequirementComparison)
        .filter(RequirementComparison.validation_run_id == run_id)
        .order_by(RequirementComparison.id.asc())
        .all()
    )


def list_runs_for_plan(db: Session, plan_id: int) -> List[ValidationRun]:
    return (
        db.query(ValidationRun)
        .filter(ValidationRun.plan_id == plan_id)
        .order_by(ValidationRun.created_at.desc())
        .all()
    )
