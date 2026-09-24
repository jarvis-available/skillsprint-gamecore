from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.constants import SYSTEM_ROLES


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class RegisterRequest(BaseModel):
    employee_id: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    system_role: str = "employee"
    department: Optional[str] = Field(default=None, max_length=100)

    @field_validator("system_role")
    @classmethod
    def _check_role(cls, v: str) -> str:
        if v not in SYSTEM_ROLES:
            raise ValueError("invalid system_role")
        return v


class TokenPayload(BaseModel):
    sub: str
    role: str


class AuthUser(BaseModel):
    id: int
    employee_id: str
    name: str
    email: EmailStr
    system_role: str
    department: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True
