from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from app.database.connection import Base


class RoleRequirement(Base):
    __tablename__ = "role_requirements"
    __table_args__ = (
        UniqueConstraint(
            "job_role_id", "requirement_id", name="uq_role_requirement"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    job_role_id = Column(
        Integer, ForeignKey("job_roles.id"), nullable=False, index=True
    )
    requirement_id = Column(
        Integer, ForeignKey("requirements.id"), nullable=False, index=True
    )

    is_mandatory = Column(Boolean, nullable=False, default=True)
    priority_override = Column(String(20), nullable=True)
    due_stage_override = Column(String(30), nullable=True)
    notes = Column(Text, nullable=True)

    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
