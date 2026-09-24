from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.core.constants import PRECEDENCE_SOURCE_TYPES


class PrecedenceRuleBase(BaseModel):
    source_type: str
    rank: int = Field(ge=1, le=1000)
    label: Optional[str] = Field(default=None, max_length=100)

    @field_validator("source_type")
    @classmethod
    def _check_type(cls, v):
        if v not in PRECEDENCE_SOURCE_TYPES:
            raise ValueError("invalid source_type")
        return v


class PrecedenceRuleCreate(PrecedenceRuleBase):
    pass


class PrecedenceRuleUpdate(BaseModel):
    rank: Optional[int] = Field(default=None, ge=1, le=1000)
    label: Optional[str] = Field(default=None, max_length=100)
    is_active: Optional[bool] = None


class PrecedenceRuleOut(PrecedenceRuleBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
