from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.constants import EXPERIENCE_LEVELS, SYSTEM_ROLES, TRAINING_STATUSES


class UserBase(BaseModel):
    employee_id: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    system_role: str = "employee"
    job_role_id: Optional[int] = None
    department: Optional[str] = Field(default=None, max_length=100)
    experience_level: Optional[str] = None
    location: Optional[str] = Field(default=None, max_length=100)
    joining_date: Optional[date] = None
    reporting_manager_id: Optional[int] = None
    previous_experience: Optional[str] = Field(default=None, max_length=500)

    @field_validator("system_role")
    @classmethod
    def _check_role(cls, v: str) -> str:
        if v not in SYSTEM_ROLES:
            raise ValueError("invalid system_role")
        return v

    @field_validator("experience_level")
    @classmethod
    def _check_exp(cls, v):
        if v is not None and v not in EXPERIENCE_LEVELS:
            raise ValueError("invalid experience_level")
        return v


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    system_role: Optional[str] = None
    job_role_id: Optional[int] = None
    department: Optional[str] = Field(default=None, max_length=100)
    experience_level: Optional[str] = None
    location: Optional[str] = Field(default=None, max_length=100)
    joining_date: Optional[date] = None
    reporting_manager_id: Optional[int] = None
    previous_experience: Optional[str] = Field(default=None, max_length=500)
    training_status: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("system_role")
    @classmethod
    def _check_role(cls, v):
        if v is not None and v not in SYSTEM_ROLES:
            raise ValueError("invalid system_role")
        return v

    @field_validator("experience_level")
    @classmethod
    def _check_exp(cls, v):
        if v is not None and v not in EXPERIENCE_LEVELS:
            raise ValueError("invalid experience_level")
        return v

    @field_validator("training_status")
    @classmethod
    def _check_status(cls, v):
        if v is not None and v not in TRAINING_STATUSES:
            raise ValueError("invalid training_status")
        return v


class UserOut(UserBase):
    id: int
    training_status: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
