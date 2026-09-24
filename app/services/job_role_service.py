from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.job_role import JobRole
from app.schemas.job_role import JobRoleCreate, JobRoleUpdate


def create_job_role(db: Session, data: JobRoleCreate) -> JobRole:
    if db.query(JobRole).filter(JobRole.name == data.name).first():
        raise AppError("Job role name already exists", 409, "job_role_taken")
    role = JobRole(
        name=data.name.strip(),
        department=data.department,
        description=data.description,
    )
    db.add(role)
    db.flush()
    return role


def list_job_roles(
    db: Session,
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
    active_only: bool = True,
) -> Tuple[List[JobRole], int]:
    q = db.query(JobRole)
    if active_only:
        q = q.filter(JobRole.is_active.is_(True))
    if search:
        like = f"%{search.strip()}%"
        q = q.filter((JobRole.name.ilike(like)) | (JobRole.department.ilike(like)))

    total = q.count()
    items = q.order_by(JobRole.name.asc()).offset(skip).limit(limit).all()
    return items, total


def get_job_role(db: Session, role_id: int) -> JobRole:
    role = db.query(JobRole).filter(JobRole.id == role_id).first()
    if role is None:
        raise AppError("Job role not found", 404, "job_role_not_found")
    return role


def update_job_role(db: Session, role_id: int, data: JobRoleUpdate) -> JobRole:
    role = get_job_role(db, role_id)
    payload = data.model_dump(exclude_unset=True)

    new_name = payload.get("name")
    if new_name and new_name != role.name:
        if db.query(JobRole).filter(JobRole.name == new_name).first():
            raise AppError("Job role name already exists", 409, "job_role_taken")

    for key, value in payload.items():
        setattr(role, key, value)

    db.flush()
    return role


def delete_job_role(db: Session, role_id: int) -> JobRole:
    role = get_job_role(db, role_id)
    role.is_active = False
    db.flush()
    return role
