from datetime import datetime, timezone
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import RegisterRequest


def register_user(db: Session, data: RegisterRequest) -> User:
    existing_email = db.query(User).filter(User.email == data.email).first()
    if existing_email:
        raise AppError("Email already registered", 409, "email_taken")

    existing_emp = (
        db.query(User).filter(User.employee_id == data.employee_id).first()
    )
    if existing_emp:
        raise AppError("Employee ID already exists", 409, "employee_id_taken")

    user = User(
        employee_id=data.employee_id,
        name=data.name,
        email=data.email,
        password_hash=hash_password(data.password),
        system_role=data.system_role,
        department=data.department,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password_hash):
        raise AppError("Invalid email or password", 401, "invalid_credentials")
    if not user.is_active:
        raise AppError("Account is inactive", 403, "inactive_account")
    return user


def issue_tokens(
    db: Session,
    user: User,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Tuple[str, str]:
    access_token, _ = create_access_token(str(user.id), user.system_role)
    raw_refresh, hashed_refresh, expires_at = create_refresh_token()

    record = RefreshToken(
        user_id=user.id,
        token_hash=hashed_refresh,
        expires_at=expires_at,
        ip_address=ip_address,
        user_agent=(user_agent or "")[:255] or None,
    )
    db.add(record)
    db.flush()
    return access_token, raw_refresh


def rotate_refresh(
    db: Session,
    raw_refresh: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Tuple[User, str, str]:
    hashed = hash_refresh_token(raw_refresh)
    record = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == hashed)
        .first()
    )
    if record is None or record.revoked:
        raise AppError("Invalid refresh token", 401, "invalid_refresh")

    if record.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise AppError("Refresh token expired", 401, "expired_refresh")

    user = db.query(User).filter(User.id == record.user_id).first()
    if user is None or not user.is_active:
        raise AppError("Account unavailable", 401, "invalid_refresh")

    record.revoked = True
    db.flush()

    access_token, new_raw = issue_tokens(db, user, ip_address, user_agent)
    return user, access_token, new_raw


def revoke_refresh(db: Session, raw_refresh: Optional[str]) -> None:
    if not raw_refresh:
        return
    hashed = hash_refresh_token(raw_refresh)
    record = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == hashed)
        .first()
    )
    if record and not record.revoked:
        record.revoked = True
        db.flush()
