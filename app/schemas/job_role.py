from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class JobRoleBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    department: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = None


class JobRoleCreate(JobRoleBase):
    pass


class JobRoleUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    department: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class JobRoleOut(JobRoleBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
