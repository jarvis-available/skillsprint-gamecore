from datetime import datetime, date

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from app.database.connection import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    employee_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(191), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)

    system_role = Column(String(30), nullable=False, default="employee")

    job_role_id = Column(Integer, ForeignKey("job_roles.id"), nullable=True)
    department = Column(String(100), nullable=True)
    experience_level = Column(String(30), nullable=True)
    location = Column(String(100), nullable=True)
    joining_date = Column(Date, nullable=True)
    reporting_manager_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    previous_experience = Column(String(500), nullable=True)
    training_status = Column(String(30), nullable=False, default="not_started")

    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    job_role = relationship("JobRole", foreign_keys=[job_role_id])
    reporting_manager = relationship("User", remote_side=[id])
