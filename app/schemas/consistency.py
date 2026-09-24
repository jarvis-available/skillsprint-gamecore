from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ConsistencyRequest(BaseModel):
    employee_user_id: int
    job_role_id: int
    max_chunks: int = Field(default=40, ge=5, le=200)


class ConsistencyRunOut(BaseModel):
    id: int
    employee_user_id: int
    job_role_id: int
    plan_a_id: Optional[int] = None
    plan_b_id: Optional[int] = None
    status: str
    consistency_score: Optional[float] = None
    matched_requirements: int
    diverged_requirements: int
    matched_module_categories: int
    matched_sources: int
    matched_assessment_topics: int
    summary_json: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    finished_at: Optional[datetime] = None

    class Config:
        from_attributes = True
