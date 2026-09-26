from typing import Optional

from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.exceptions import AppError
from app.core.security import (
    REFRESH_COOKIE,
    clear_auth_cookies,
    hash_password,
    set_auth_cookies,
    verify_password,
)
from app.database.connection import get_db
from app.models.user import User
from app.schemas.auth import AuthUser, LoginRequest, RegisterRequest
from app.schemas.user import PasswordChangeRequest
from app.services import audit_service, auth_service


router = APIRouter(prefix="/api/auth", tags=["auth"])


def _client_ip(request: Request) -> Optional[str]:
    if request.client:
        return request.client.host
    return None


@router.post("/register", response_model=AuthUser, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    user = auth_service.register_user(db, payload)
    access, refresh = auth_service.issue_tokens(
        db, user, _client_ip(request), request.headers.get("user-agent")
    )
    audit_service.record(
        db, user.id, "user.register", "user", user.id, ip_address=_client_ip(request)
    )
    db.commit()
    db.refresh(user)
    set_auth_cookies(response, access, refresh)
    return user


@router.post("/login", response_model=AuthUser)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    user = auth_service.authenticate(db, payload.email, payload.password)
    access, refresh = auth_service.issue_tokens(
        db, user, _client_ip(request), request.headers.get("user-agent")
    )
    audit_service.record(
        db, user.id, "user.login", "user", user.id, ip_address=_client_ip(request)
    )
    db.commit()
    db.refresh(user)
    set_auth_cookies(response, access, refresh)
    return user


@router.post("/refresh", response_model=AuthUser)
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    refresh_token: Optional[str] = Cookie(default=None, alias=REFRESH_COOKIE),
):
    if not refresh_token:
        from app.core.exceptions import AppError

        raise AppError("Missing refresh token", 401, "missing_refresh")

    user, access, new_refresh = auth_service.rotate_refresh(
        db, refresh_token, _client_ip(request), request.headers.get("user-agent")
    )
    db.commit()
    db.refresh(user)
    set_auth_cookies(response, access, new_refresh)
    return user


@router.post("/logout")
def logout(
    response: Response,
    db: Session = Depends(get_db),
    refresh_token: Optional[str] = Cookie(default=None, alias=REFRESH_COOKIE),
):
    auth_service.revoke_refresh(db, refresh_token)
    db.commit()
    clear_auth_cookies(response)
    return {"detail": "logged_out"}


@router.get("/me", response_model=AuthUser)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/change-password")
def change_password(
    payload: PasswordChangeRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise AppError("Current password is incorrect", 401, "invalid_current_password")
    if payload.new_password == payload.current_password:
        raise AppError("New password must differ from current password", 400, "same_password")
    current_user.password_hash = hash_password(payload.new_password)
    auth_service.revoke_all_refresh_for_user(db, current_user.id)
    audit_service.record(
        db, current_user.id, "user.change_password", "user", current_user.id,
        ip_address=_client_ip(request),
    )
    db.commit()
    return {"detail": "password_changed"}
