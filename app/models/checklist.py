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


class Checklist(Base):
    __tablename__ = "checklists"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(
        Integer, ForeignKey("onboarding_plans.id"), nullable=False, index=True
    )
    stage_id = Column(Integer, ForeignKey("plan_stages.id"), nullable=True)

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    order_index = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class ChecklistItem(Base):
    __tablename__ = "checklist_items"

    id = Column(Integer, primary_key=True, index=True)
    checklist_id = Column(
        Integer, ForeignKey("checklists.id"), nullable=False, index=True
    )

    activity = Column(Text, nullable=False)
    is_required = Column(Boolean, nullable=False, default=True)
    due_stage = Column(String(30), nullable=True)

    source_document_id = Column(
        Integer, ForeignKey("documents.id"), nullable=True
    )
    source_section = Column(String(100), nullable=True)
    responsible_role = Column(String(100), nullable=True)

    order_index = Column(Integer, nullable=False, default=0)
