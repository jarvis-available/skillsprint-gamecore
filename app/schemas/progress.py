from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from app.core.constants import (
    COMPLETION_STATUSES,
    PROGRESS_ASSESSMENTS,
    RECOMMENDATION_STATUSES,
    RECOMMENDATION_TYPES,
)


class CompletionUpdate(BaseModel):
    status: str
    notes: Optional[str] = Field(default=None, max_length=2000)
    completion_notes: Optional[str] = Field(default=None, max_length=2000)
    evidence_url: Optional[str] = Field(default=None, max_length=500)

    @field_validator("status")
    @classmethod
    def _st(cls, v):
        if v not in COMPLETION_STATUSES:
            raise ValueError("invalid status")
        return v


class ChecklistToggle(BaseModel):
    checked: bool


class QuizAnswer(BaseModel):
    question_id: int
    option_ids: List[int] = Field(default_factory=list)


class QuizAttemptSubmission(BaseModel):
    answers: List[QuizAnswer]


class QuizAttemptOut(BaseModel):
    id: int
    quiz_id: int
    employee_user_id: int
    score: float
    max_score: float
    percentage: float
    passed: bool
    submitted_at: datetime
    grading_json: Optional[str] = None

    class Config:
        from_attributes = True


class RubricScoreItem(BaseModel):
    rubric_id: int
    score: float = Field(ge=0.0)


class AssessmentAttemptSubmission(BaseModel):
    rubric_scores: List[RubricScoreItem]
    notes: Optional[str] = Field(default=None, max_length=2000)


class AssessmentAttemptOut(BaseModel):
    id: int
    assessment_id: int
    employee_user_id: int
    total_score: float
    max_score: float
    percentage: float
    passed: bool
    notes: Optional[str] = None
    graded_by: Optional[int] = None
    submitted_at: datetime

    class Config:
        from_attributes = True


class PlanProgressSummary(BaseModel):
    plan_id: int
    employee_user_id: int
    overall_percentage: float
    module_percentage: float
    task_percentage: float
    checklist_percentage: float
    quiz_average: Optional[float] = None
    assessment_average: Optional[float] = None
    modules_completed: int
    modules_total: int
    tasks_completed: int
    tasks_total: int
    checklist_items_completed: int
    checklist_items_total: int
    quizzes_attempted: int
    quizzes_total: int
    assessments_attempted: int
    assessments_total: int
    weak_areas: List[Dict] = []
    progress_assessment: str

    @field_validator("progress_assessment")
    @classmethod
    def _pa(cls, v):
        if v not in PROGRESS_ASSESSMENTS:
            raise ValueError("invalid progress_assessment")
        return v


class RecommendationOut(BaseModel):
    id: int
    plan_id: int
    employee_user_id: int
    recommendation_type: str
    reason: str
    target_module_id: Optional[int] = None
    target_task_id: Optional[int] = None
    target_requirement_id: Optional[int] = None
    priority: str
    status: str
    score: Optional[float] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RecommendationUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def _st(cls, v):
        if v not in RECOMMENDATION_STATUSES:
            raise ValueError("invalid status")
        return v
