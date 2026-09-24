from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.core.constants import (
    ASSESSMENT_TYPES,
    DUE_STAGES,
    EXPERIENCE_LEVELS,
    QUESTION_TYPES,
)


VALID_STAGES = set(DUE_STAGES)
VALID_DIFFICULTY = set(EXPERIENCE_LEVELS)


class AIOption(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    is_correct: bool = False


class AIQuestion(BaseModel):
    question_type: str
    prompt_text: str = Field(min_length=1, max_length=4000)
    difficulty: Optional[str] = None
    source_document_id: Optional[int] = None
    source_section: Optional[str] = Field(default=None, max_length=100)
    explanation: Optional[str] = None
    points: int = Field(default=1, ge=1, le=100)
    options: List[AIOption] = Field(default_factory=list)

    @field_validator("question_type")
    @classmethod
    def _qtype(cls, v):
        if v not in QUESTION_TYPES:
            raise ValueError("invalid question_type")
        return v

    @field_validator("difficulty")
    @classmethod
    def _diff(cls, v):
        if v is not None and v not in VALID_DIFFICULTY:
            raise ValueError("invalid difficulty")
        return v


class AIQuiz(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    passing_score: int = Field(default=70, ge=0, le=100)
    module_code: Optional[str] = None
    questions: List[AIQuestion] = Field(default_factory=list)


class AIObjective(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


class AIActivity(BaseModel):
    description: str = Field(min_length=1, max_length=2000)


class AIModule(BaseModel):
    module_code: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=255)
    purpose: Optional[str] = None
    key_concepts: Optional[str] = None
    estimated_minutes: Optional[int] = Field(default=None, ge=1, le=100000)
    completion_criteria: Optional[str] = None
    stage: Optional[str] = None
    requirement_id: Optional[int] = None
    is_mandatory: bool = False
    source_document_id: Optional[int] = None
    source_section: Optional[str] = Field(default=None, max_length=100)
    source_chunk_ids: List[int] = Field(default_factory=list)
    objectives: List[str] = Field(default_factory=list)
    activities: List[str] = Field(default_factory=list)

    @field_validator("stage")
    @classmethod
    def _stage(cls, v):
        if v is not None and v not in VALID_STAGES:
            raise ValueError("invalid stage")
        return v


class AIChecklistItem(BaseModel):
    activity: str = Field(min_length=1, max_length=1000)
    is_required: bool = True
    due_stage: Optional[str] = None
    source_document_id: Optional[int] = None
    source_section: Optional[str] = Field(default=None, max_length=100)
    responsible_role: Optional[str] = Field(default=None, max_length=100)

    @field_validator("due_stage")
    @classmethod
    def _stage(cls, v):
        if v is not None and v not in VALID_STAGES:
            raise ValueError("invalid due_stage")
        return v


class AIChecklist(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    stage: Optional[str] = None
    items: List[AIChecklistItem] = Field(default_factory=list)

    @field_validator("stage")
    @classmethod
    def _stage(cls, v):
        if v is not None and v not in VALID_STAGES:
            raise ValueError("invalid stage")
        return v


class AITask(BaseModel):
    task_code: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    expected_outcome: Optional[str] = None
    completion_criteria: Optional[str] = None
    difficulty: Optional[str] = None
    due_stage: Optional[str] = None
    is_scenario: bool = False
    requirement_id: Optional[int] = None
    source_document_id: Optional[int] = None
    source_section: Optional[str] = Field(default=None, max_length=100)

    @field_validator("difficulty")
    @classmethod
    def _diff(cls, v):
        if v is not None and v not in VALID_DIFFICULTY:
            raise ValueError("invalid difficulty")
        return v

    @field_validator("due_stage")
    @classmethod
    def _stage(cls, v):
        if v is not None and v not in VALID_STAGES:
            raise ValueError("invalid due_stage")
        return v


class AIRubric(BaseModel):
    criterion: str = Field(min_length=1, max_length=2000)
    weight: float = Field(default=1.0, ge=0.0, le=100.0)
    expected_performance: Optional[str] = None
    pass_condition: Optional[str] = None


class AIAssessment(BaseModel):
    assessment_type: str
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    passing_score: int = Field(default=70, ge=0, le=100)
    module_code: Optional[str] = None
    source_document_id: Optional[int] = None
    source_section: Optional[str] = Field(default=None, max_length=100)
    rubric: List[AIRubric] = Field(default_factory=list)

    @field_validator("assessment_type")
    @classmethod
    def _atype(cls, v):
        if v not in ASSESSMENT_TYPES:
            raise ValueError("invalid assessment_type")
        return v


class AIStage(BaseModel):
    stage: str
    description: Optional[str] = None

    @field_validator("stage")
    @classmethod
    def _stage(cls, v):
        if v not in VALID_STAGES:
            raise ValueError("invalid stage")
        return v


class AIOnboardingPlan(BaseModel):
    plan_summary: Optional[str] = None
    stages: List[AIStage] = Field(default_factory=list)
    modules: List[AIModule] = Field(default_factory=list)
    checklists: List[AIChecklist] = Field(default_factory=list)
    tasks: List[AITask] = Field(default_factory=list)
    quizzes: List[AIQuiz] = Field(default_factory=list)
    assessments: List[AIAssessment] = Field(default_factory=list)
    notes: Optional[str] = None
