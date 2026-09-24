from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from app.database.connection import Base


class ModuleCompletion(Base):
    __tablename__ = "module_completions"
    __table_args__ = (
        UniqueConstraint("module_id", "employee_user_id", name="uq_module_completion"),
    )

    id = Column(Integer, primary_key=True, index=True)

    module_id = Column(Integer, ForeignKey("learning_modules.id"), nullable=False, index=True)
    employee_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    status = Column(String(20), nullable=False, default="not_started")
    notes = Column(Text, nullable=True)

    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class TaskCompletion(Base):
    __tablename__ = "task_completions"
    __table_args__ = (
        UniqueConstraint("task_id", "employee_user_id", name="uq_task_completion"),
    )

    id = Column(Integer, primary_key=True, index=True)

    task_id = Column(Integer, ForeignKey("plan_tasks.id"), nullable=False, index=True)
    employee_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    status = Column(String(20), nullable=False, default="not_started")
    completion_notes = Column(Text, nullable=True)
    evidence_url = Column(String(500), nullable=True)

    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class ChecklistItemCompletion(Base):
    __tablename__ = "checklist_item_completions"
    __table_args__ = (
        UniqueConstraint(
            "item_id", "employee_user_id", name="uq_checklist_item_completion"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    item_id = Column(Integer, ForeignKey("checklist_items.id"), nullable=False, index=True)
    employee_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    checked = Column(Boolean, nullable=False, default=False)
    completed_at = Column(DateTime, nullable=True)
