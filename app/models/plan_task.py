from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)

from app.database.connection import Base


class PlanTask(Base):
    __tablename__ = "plan_tasks"

    id = Column(Integer, primary_key=True, index=True)

    plan_id = Column(
        Integer, ForeignKey("onboarding_plans.id"), nullable=False, index=True
    )
    stage_id = Column(Integer, ForeignKey("plan_stages.id"), nullable=True)
    requirement_id = Column(
        Integer, ForeignKey("requirements.id"), nullable=True, index=True
    )

    task_code = Column(String(50), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    expected_outcome = Column(Text, nullable=True)
    completion_criteria = Column(Text, nullable=True)

    difficulty = Column(String(20), nullable=True)
    due_stage = Column(String(30), nullable=True)

    source_document_id = Column(
        Integer, ForeignKey("documents.id"), nullable=True
    )
    source_section = Column(String(100), nullable=True)

    is_scenario = Column(Boolean, nullable=False, default=False)
    order_index = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
