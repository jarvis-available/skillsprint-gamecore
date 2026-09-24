from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.core.constants import (
    DUE_STAGES,
    MUST_TYPES,
    PRIORITIES,
    REQUIREMENT_TYPES,
)


class RequirementBase(BaseModel):
    req_code: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None

    requirement_type: str
    must_type: str
    priority: str = "medium"
    due_stage: Optional[str] = None

    competency: Optional[str] = Field(default=None, max_length=255)
    assessment_topic: Optional[str] = Field(default=None, max_length=255)

    source_document_id: Optional[int] = None
    source_version_id: Optional[int] = None
    source_chunk_id: Optional[int] = None
    source_section: Optional[str] = Field(default=None, max_length=100)

    @field_validator("requirement_type")
    @classmethod
    def _check_type(cls, v):
        if v not in REQUIREMENT_TYPES:
            raise ValueError("invalid requirement_type")
        return v

    @field_validator("must_type")
    @classmethod
    def _check_must(cls, v):
        if v not in MUST_TYPES:
            raise ValueError("invalid must_type")
        return v

    @field_validator("priority")
    @classmethod
    def _check_prio(cls, v):
        if v not in PRIORITIES:
            raise ValueError("invalid priority")
        return v

    @field_validator("due_stage")
    @classmethod
    def _check_stage(cls, v):
        if v is not None and v not in DUE_STAGES:
            raise ValueError("invalid due_stage")
        return v


class RequirementCreate(RequirementBase):
    pass


class RequirementUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    requirement_type: Optional[str] = None
    must_type: Optional[str] = None
    priority: Optional[str] = None
    due_stage: Optional[str] = None
    competency: Optional[str] = Field(default=None, max_length=255)
    assessment_topic: Optional[str] = Field(default=None, max_length=255)
    source_document_id: Optional[int] = None
    source_version_id: Optional[int] = None
    source_chunk_id: Optional[int] = None
    source_section: Optional[str] = Field(default=None, max_length=100)
    is_active: Optional[bool] = None

    @field_validator("requirement_type")
    @classmethod
    def _check_type(cls, v):
        if v is not None and v not in REQUIREMENT_TYPES:
            raise ValueError("invalid requirement_type")
        return v

    @field_validator("must_type")
    @classmethod
    def _check_must(cls, v):
        if v is not None and v not in MUST_TYPES:
            raise ValueError("invalid must_type")
        return v

    @field_validator("priority")
    @classmethod
    def _check_prio(cls, v):
        if v is not None and v not in PRIORITIES:
            raise ValueError("invalid priority")
        return v

    @field_validator("due_stage")
    @classmethod
    def _check_stage(cls, v):
        if v is not None and v not in DUE_STAGES:
            raise ValueError("invalid due_stage")
        return v


class RequirementOut(RequirementBase):
    id: int
    is_active: bool
    is_mandatory_derived: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PrerequisiteLink(BaseModel):
    prerequisite_id: int


class PrerequisiteOut(BaseModel):
    id: int
    requirement_id: int
    prerequisite_id: int

    class Config:
        from_attributes = True


class RequirementWithPrereqs(RequirementOut):
    prerequisite_ids: List[int] = []
