SYSTEM_ROLES = (
    "admin",
    "training_manager",
    "reviewer",
    "manager",
    "employee",
)

EXPERIENCE_LEVELS = ("beginner", "intermediate", "advanced")

TRAINING_STATUSES = (
    "not_started",
    "in_progress",
    "on_track",
    "requires_attention",
    "behind_schedule",
    "assessment_required",
    "completed",
)

DOCUMENT_TYPES = (
    "policy",
    "hr_policy",
    "leave_policy",
    "info_security",
    "workplace_conduct",
    "data_privacy",
    "sop",
    "process_manual",
    "role_description",
    "faq",
    "compliance",
    "handbook",
    "department_guideline",
    "safety",
    "other",
)

ALLOWED_MIME_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
}

ALLOWED_EXTENSIONS = {".pdf", ".docx"}

REQUIREMENT_TYPES = (
    "policy",
    "process",
    "competency",
    "task",
    "assessment",
    "knowledge",
)

MUST_TYPES = (
    "must_know",
    "must_complete",
    "must_demonstrate",
    "must_acknowledge",
    "recommended",
    "optional",
    "not_applicable",
)

MANDATORY_MUST_TYPES = {
    "must_know",
    "must_complete",
    "must_demonstrate",
    "must_acknowledge",
}

PRIORITIES = ("low", "medium", "high", "critical")

DUE_STAGES = (
    "day_1",
    "week_1",
    "week_2",
    "first_30_days",
    "first_60_days",
    "first_90_days",
)

PRECEDENCE_SOURCE_TYPES = (
    "policy",
    "hr_policy",
    "info_security",
    "workplace_conduct",
    "data_privacy",
    "sop",
    "process_manual",
    "compliance",
    "role_description",
    "handbook",
    "department_guideline",
    "faq",
    "safety",
    "informal_guidance",
    "other",
)

DEFAULT_PRECEDENCE_ORDER = (
    "policy",
    "compliance",
    "info_security",
    "data_privacy",
    "hr_policy",
    "workplace_conduct",
    "sop",
    "process_manual",
    "role_description",
    "department_guideline",
    "handbook",
    "safety",
    "faq",
    "informal_guidance",
    "other",
)

PLAN_STATUSES = (
    "draft",
    "generating",
    "ready",
    "verified",
    "verified_with_warning",
    "partially_verified",
    "incomplete",
    "unsupported",
    "contradictory",
    "manual_review",
    "archived",
)

QUESTION_TYPES = (
    "multiple_choice",
    "multiple_response",
    "true_false",
    "scenario",
)

ASSESSMENT_TYPES = (
    "knowledge",
    "practical",
    "scenario",
    "role_specific",
)

GENERATION_STATUSES = (
    "running",
    "succeeded",
    "failed",
    "timeout",
    "invalid_json",
    "schema_mismatch",
)

VERIFICATION_STATUSES = (
    "verified",
    "verified_with_warning",
    "partially_verified",
    "source_support_missing",
    "requirement_missing",
    "unsupported_requirement",
    "outdated_source",
    "contradiction_detected",
    "manual_review_required",
    "incomplete",
)

FINDING_SEVERITIES = ("info", "warning", "error")

FINDING_ISSUE_TYPES = (
    "coverage_missing",
    "source_missing",
    "source_invalid",
    "outdated_source",
    "hallucination",
    "contradiction",
    "duplicate",
    "role_irrelevance",
    "sequence_violation",
    "distractor_conflict",
    "requirement_unsupported",
    "requirement_covered",
    "schema_gap",
)

VALIDATION_ENTITY_TYPES = (
    "plan",
    "stage",
    "module",
    "objective",
    "activity",
    "checklist",
    "checklist_item",
    "task",
    "quiz",
    "quiz_question",
    "assessment",
    "rubric",
    "requirement",
)

VALIDATION_RUN_STATUSES = ("running", "succeeded", "failed")

FINDING_REVIEW_DECISIONS = (
    "acknowledge",
    "resolve",
    "reject",
    "escalate",
)

PLAN_REVIEW_DECISIONS = (
    "approve",
    "reject",
    "request_regeneration",
    "mark_manual_review",
    "override_status",
    "comment",
)

CONSISTENCY_RUN_STATUSES = ("running", "succeeded", "failed")

COMPLETION_STATUSES = ("not_started", "in_progress", "completed", "skipped")

ATTEMPT_STATUSES = ("submitted", "graded", "failed_validation")

RECOMMENDATION_TYPES = (
    "revision_module",
    "additional_quiz",
    "additional_task",
    "advanced_module",
    "manager_review",
    "revisit_prerequisite",
)

RECOMMENDATION_STATUSES = ("pending", "completed", "dismissed")

PROGRESS_ASSESSMENTS = (
    "on_track",
    "requires_attention",
    "behind_schedule",
    "assessment_required",
    "completed",
)


