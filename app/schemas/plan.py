from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class GenerateRequest(BaseModel):
    employee_user_id: int
    job_role_id: int
    max_chunks: int = 40
    plan_note: Optional[str] = None


class PlanStageOut(BaseModel):
    id: int
    stage: str
    order_index: int
    description: Optional[str] = None

    class Config:
        from_attributes = True


class ObjectiveOut(BaseModel):
    id: int
    text: str
    order_index: int

    class Config:
        from_attributes = True


class ActivityOut(BaseModel):
    id: int
    description: str
    order_index: int

    class Config:
        from_attributes = True


class ModuleOut(BaseModel):
    id: int
    module_code: str
    title: str
    purpose: Optional[str] = None
    key_concepts: Optional[str] = None
    estimated_minutes: Optional[int] = None
    completion_criteria: Optional[str] = None
    stage_id: Optional[int] = None
    requirement_id: Optional[int] = None
    is_mandatory: bool
    source_document_id: Optional[int] = None
    source_section: Optional[str] = None
    source_chunk_ids: Optional[str] = None
    order_index: int
    objectives: List[ObjectiveOut] = []
    activities: List[ActivityOut] = []

    class Config:
        from_attributes = True


class ChecklistItemOut(BaseModel):
    id: int
    activity: str
    is_required: bool
    due_stage: Optional[str] = None
    source_document_id: Optional[int] = None
    source_section: Optional[str] = None
    responsible_role: Optional[str] = None
    order_index: int

    class Config:
        from_attributes = True


class ChecklistOut(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    stage_id: Optional[int] = None
    order_index: int
    items: List[ChecklistItemOut] = []

    class Config:
        from_attributes = True


class TaskOut(BaseModel):
    id: int
    task_code: str
    title: str
    description: Optional[str] = None
    expected_outcome: Optional[str] = None
    completion_criteria: Optional[str] = None
    difficulty: Optional[str] = None
    due_stage: Optional[str] = None
    is_scenario: bool
    requirement_id: Optional[int] = None
    source_document_id: Optional[int] = None
    source_section: Optional[str] = None
    order_index: int

    class Config:
        from_attributes = True


class QuizOptionOut(BaseModel):
    id: int
    text: str
    is_correct: bool
    order_index: int

    class Config:
        from_attributes = True


class QuizQuestionOut(BaseModel):
    id: int
    question_type: str
    prompt_text: str
    difficulty: Optional[str] = None
    source_document_id: Optional[int] = None
    source_section: Optional[str] = None
    explanation: Optional[str] = None
    points: int
    order_index: int
    options: List[QuizOptionOut] = []

    class Config:
        from_attributes = True


class QuizOut(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    passing_score: int
    total_points: int
    module_id: Optional[int] = None
    questions: List[QuizQuestionOut] = []

    class Config:
        from_attributes = True


class RubricOut(BaseModel):
    id: int
    criterion: str
    weight: float
    expected_performance: Optional[str] = None
    pass_condition: Optional[str] = None
    order_index: int

    class Config:
        from_attributes = True


class AssessmentOut(BaseModel):
    id: int
    assessment_type: str
    title: str
    description: Optional[str] = None
    passing_score: int
    module_id: Optional[int] = None
    source_document_id: Optional[int] = None
    source_section: Optional[str] = None
    rubric: List[RubricOut] = []

    class Config:
        from_attributes = True


class GenerationRunOut(BaseModel):
    id: int
    provider: str
    model_name: str
    status: str
    parsed_ok: bool
    parse_error: Optional[str] = None
    retries: int
    latency_ms: Optional[int] = None
    token_estimate: Optional[int] = None
    prompt_template_id: Optional[int] = None
    prompt_version_id: Optional[int] = None
    source_document_ids: Optional[str] = None
    input_summary: Optional[str] = None
    created_at: datetime
    finished_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PlanSummary(BaseModel):
    id: int
    plan_code: str
    employee_user_id: int
    employee_name: Optional[str] = None
    job_role_id: int
    job_role_name: Optional[str] = None
    status: str
    module_count: int
    task_count: int
    quiz_count: int
    assessment_count: int
    created_at: datetime


class PlanDetail(BaseModel):
    id: int
    plan_code: str
    employee_user_id: int
    employee_name: Optional[str] = None
    job_role_id: int
    job_role_name: Optional[str] = None
    status: str
    notes: Optional[str] = None
    summary_json: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    stages: List[PlanStageOut] = []
    modules: List[ModuleOut] = []
    checklists: List[ChecklistOut] = []
    tasks: List[TaskOut] = []
    quizzes: List[QuizOut] = []
    assessments: List[AssessmentOut] = []
    generation_run: Optional[GenerationRunOut] = None
