from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.core.constants import DUE_STAGES, PRIORITIES


class RoleRequirementBase(BaseModel):
    job_role_id: int
    requirement_id: int
    is_mandatory: bool = True
    priority_override: Optional[str] = None
    due_stage_override: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("priority_override")
    @classmethod
    def _check_prio(cls, v):
        if v is not None and v not in PRIORITIES:
            raise ValueError("invalid priority_override")
        return v

    @field_validator("due_stage_override")
    @classmethod
    def _check_stage(cls, v):
        if v is not None and v not in DUE_STAGES:
            raise ValueError("invalid due_stage_override")
        return v


class RoleRequirementCreate(RoleRequirementBase):
    pass


class RoleRequirementUpdate(BaseModel):
    is_mandatory: Optional[bool] = None
    priority_override: Optional[str] = None
    due_stage_override: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("priority_override")
    @classmethod
    def _check_prio(cls, v):
        if v is not None and v not in PRIORITIES:
            raise ValueError("invalid priority_override")
        return v

    @field_validator("due_stage_override")
    @classmethod
    def _check_stage(cls, v):
        if v is not None and v not in DUE_STAGES:
            raise ValueError("invalid due_stage_override")
        return v


class RoleRequirementOut(BaseModel):
    id: int
    job_role_id: int
    requirement_id: int
    is_mandatory: bool
    priority_override: Optional[str] = None
    due_stage_override: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MatrixCell(BaseModel):
    req_code: str
    requirement_id: int
    title: str
    requirement_type: str
    must_type: str
    is_mandatory: bool
    effective_priority: str
    effective_due_stage: Optional[str] = None
    source_document_id: Optional[int] = None
    source_section: Optional[str] = None


class MatrixRow(BaseModel):
    job_role_id: int
    job_role_name: str
    department: Optional[str] = None
    cells: List[MatrixCell]
    mandatory_count: int
    total_count: int
