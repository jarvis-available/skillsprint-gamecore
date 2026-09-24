from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin
from app.database.connection import get_db
from app.models.user import User
from app.schemas.user import (
    PasswordChangeRequest,
    UserCreate,
    UserOut,
    UserUpdate,
)
from app.services import audit_service, user_service


router = APIRouter(prefix="/api/users", tags=["users"])


def _client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


@router.get("")
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: Optional[str] = None,
    system_role: Optional[str] = None,
    department: Optional[str] = None,
):
    items, total = user_service.list_users(
        db, skip, limit, search, system_role, department
    )
    return {
        "total": total,
        "items": [UserOut.model_validate(u) for u in items],
    }


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin),
):
    user = user_service.create_user(db, payload)
    audit_service.record(
        db, current.id, "user.create", "user", user.id, ip_address=_client_ip(request)
    )
    db.commit()
    db.refresh(user)
    return user


@router.get("/me", response_model=UserOut)
def read_me(current: User = Depends(get_current_user)):
    return current


@router.put("/me/password")
def change_my_password(
    payload: PasswordChangeRequest,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    user_service.change_password(
        db, current, payload.current_password, payload.new_password
    )
    audit_service.record(
        db,
        current.id,
        "user.password_change",
        "user",
        current.id,
        ip_address=_client_ip(request),
    )
    db.commit()
    return {"detail": "password_updated"}


@router.get("/{user_id}", response_model=UserOut)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return user_service.get_user(db, user_id)


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin),
):
    user = user_service.update_user(db, user_id, payload)
    audit_service.record(
        db, current.id, "user.update", "user", user.id, ip_address=_client_ip(request)
    )
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}")
def deactivate_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin),
):
    if user_id == current.id:
        from app.core.exceptions import AppError

        raise AppError("You cannot deactivate yourself", 400, "self_deactivate")
    user_service.deactivate_user(db, user_id)
    audit_service.record(
        db,
        current.id,
        "user.deactivate",
        "user",
        user_id,
        ip_address=_client_ip(request),
    )
    db.commit()
    return {"detail": "user_deactivated"}
