from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.core.constants import (
    FINDING_REVIEW_DECISIONS,
    FINDING_SEVERITIES,
    PLAN_REVIEW_DECISIONS,
    VERIFICATION_STATUSES,
)


class FindingReviewCreate(BaseModel):
    decision: str
    comment: Optional[str] = Field(default=None, max_length=2000)
    override_severity: Optional[str] = None

    @field_validator("decision")
    @classmethod
    def _dec(cls, v):
        if v not in FINDING_REVIEW_DECISIONS:
            raise ValueError("invalid decision")
        return v

    @field_validator("override_severity")
    @classmethod
    def _sev(cls, v):
        if v is not None and v not in FINDING_SEVERITIES:
            raise ValueError("invalid override_severity")
        return v


class FindingReviewOut(BaseModel):
    id: int
    finding_id: int
    reviewed_by: int
    decision: str
    comment: Optional[str] = None
    override_severity: Optional[str] = None
    prior_severity: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PlanReviewCreate(BaseModel):
    decision: str
    comment: Optional[str] = Field(default=None, max_length=2000)
    new_status: Optional[str] = None
    validation_run_id: Optional[int] = None

    @field_validator("decision")
    @classmethod
    def _dec(cls, v):
        if v not in PLAN_REVIEW_DECISIONS:
            raise ValueError("invalid decision")
        return v

    @field_validator("new_status")
    @classmethod
    def _stat(cls, v):
        if v is not None and v not in VERIFICATION_STATUSES:
            raise ValueError("invalid new_status")
        return v


class PlanReviewOut(BaseModel):
    id: int
    plan_id: int
    validation_run_id: Optional[int] = None
    reviewed_by: int
    decision: str
    comment: Optional[str] = None
    prior_status: Optional[str] = None
    new_status: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
