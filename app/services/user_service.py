from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.security import hash_password, verify_password
from app.models.job_role import JobRole
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


def _ensure_job_role(db: Session, job_role_id: Optional[int]) -> None:
    if job_role_id is None:
        return
    exists = db.query(JobRole).filter(JobRole.id == job_role_id).first()
    if not exists:
        raise AppError("job_role_id not found", 404, "job_role_not_found")


def _ensure_manager(db: Session, manager_id: Optional[int]) -> None:
    if manager_id is None:
        return
    exists = db.query(User).filter(User.id == manager_id).first()
    if not exists:
        raise AppError("reporting_manager_id not found", 404, "manager_not_found")


def create_user(db: Session, data: UserCreate) -> User:
    if db.query(User).filter(User.email == data.email).first():
        raise AppError("Email already registered", 409, "email_taken")
    if db.query(User).filter(User.employee_id == data.employee_id).first():
        raise AppError("Employee ID already exists", 409, "employee_id_taken")

    _ensure_job_role(db, data.job_role_id)
    _ensure_manager(db, data.reporting_manager_id)

    user = User(
        employee_id=data.employee_id,
        name=data.name,
        email=data.email,
        password_hash=hash_password(data.password),
        system_role=data.system_role,
        job_role_id=data.job_role_id,
        department=data.department,
        experience_level=data.experience_level,
        location=data.location,
        joining_date=data.joining_date,
        reporting_manager_id=data.reporting_manager_id,
        previous_experience=data.previous_experience,
    )
    db.add(user)
    db.flush()
    return user


def list_users(
    db: Session,
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
    system_role: Optional[str] = None,
    department: Optional[str] = None,
) -> Tuple[List[User], int]:
    q = db.query(User)
    if search:
        like = f"%{search.strip()}%"
        q = q.filter(
            (User.name.ilike(like))
            | (User.email.ilike(like))
            | (User.employee_id.ilike(like))
        )
    if system_role:
        q = q.filter(User.system_role == system_role)
    if department:
        q = q.filter(User.department == department)

    total = q.count()
    items = q.order_by(User.created_at.desc()).offset(skip).limit(limit).all()
    return items, total


def get_user(db: Session, user_id: int) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise AppError("User not found", 404, "user_not_found")
    return user


def update_user(db: Session, user_id: int, data: UserUpdate) -> User:
    user = get_user(db, user_id)
    payload = data.model_dump(exclude_unset=True)

    if "job_role_id" in payload:
        _ensure_job_role(db, payload["job_role_id"])
    if "reporting_manager_id" in payload:
        if payload["reporting_manager_id"] == user_id:
            raise AppError("User cannot report to themselves", 400, "invalid_manager")
        _ensure_manager(db, payload["reporting_manager_id"])

    for key, value in payload.items():
        setattr(user, key, value)

    db.flush()
    return user


def deactivate_user(db: Session, user_id: int) -> User:
    user = get_user(db, user_id)
    user.is_active = False
    db.flush()
    return user


def change_password(
    db: Session, user: User, current_password: str, new_password: str
) -> None:
    if not verify_password(current_password, user.password_hash):
        raise AppError("Current password is incorrect", 400, "invalid_password")
    user.password_hash = hash_password(new_password)
    db.flush()
