import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import bcrypt
from fastapi import Response
from jose import JWTError, jwt

from app.core.config import settings


ACCESS_COOKIE = "sk_access"
REFRESH_COOKIE = "sk_refresh"

_BCRYPT_MAX_BYTES = 72


def _prepare_password(password: str) -> bytes:
    raw = password.encode("utf-8")
    if len(raw) > _BCRYPT_MAX_BYTES:
        raw = raw[:_BCRYPT_MAX_BYTES]
    return raw


def hash_password(password: str) -> str:
    hashed = bcrypt.hashpw(_prepare_password(password), bcrypt.gensalt(rounds=12))
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_prepare_password(plain), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(subject: str, role: str) -> Tuple[str, datetime]:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "sub": subject,
        "role": role,
        "type": "access",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, expire


def create_refresh_token() -> Tuple[str, str, datetime]:
    raw = secrets.token_urlsafe(48)
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    return raw, hashed, expire


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None


def set_auth_cookies(response: Response, access: str, refresh: str) -> None:
    common = {
        "httponly": True,
        "secure": settings.COOKIE_SECURE,
        "samesite": settings.COOKIE_SAMESITE,
    }
    if settings.COOKIE_DOMAIN:
        common["domain"] = settings.COOKIE_DOMAIN

    response.set_cookie(
        key=ACCESS_COOKIE,
        value=access,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
        **common,
    )
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=refresh,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/api/auth",
        **common,
    )


def clear_auth_cookies(response: Response) -> None:
    common = {"httponly": True, "secure": settings.COOKIE_SECURE, "samesite": settings.COOKIE_SAMESITE}
    if settings.COOKIE_DOMAIN:
        common["domain"] = settings.COOKIE_DOMAIN
    response.delete_cookie(ACCESS_COOKIE, path="/", **common)
    response.delete_cookie(REFRESH_COOKIE, path="/api/auth", **common)
