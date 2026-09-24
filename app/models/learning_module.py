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


class LearningModule(Base):
    __tablename__ = "learning_modules"

    id = Column(Integer, primary_key=True, index=True)

    plan_id = Column(
        Integer, ForeignKey("onboarding_plans.id"), nullable=False, index=True
    )
    stage_id = Column(Integer, ForeignKey("plan_stages.id"), nullable=True)
    requirement_id = Column(
        Integer, ForeignKey("requirements.id"), nullable=True, index=True
    )

    module_code = Column(String(50), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    purpose = Column(Text, nullable=True)
    key_concepts = Column(Text, nullable=True)
    estimated_minutes = Column(Integer, nullable=True)
    completion_criteria = Column(Text, nullable=True)

    source_document_id = Column(
        Integer, ForeignKey("documents.id"), nullable=True, index=True
    )
    source_section = Column(String(100), nullable=True)
    source_chunk_ids = Column(String(500), nullable=True)

    is_mandatory = Column(Boolean, nullable=False, default=False)
    order_index = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class LearningObjective(Base):
    __tablename__ = "learning_objectives"

    id = Column(Integer, primary_key=True, index=True)
    module_id = Column(
        Integer, ForeignKey("learning_modules.id"), nullable=False, index=True
    )
    text = Column(Text, nullable=False)
    order_index = Column(Integer, nullable=False, default=0)


class ModuleActivity(Base):
    __tablename__ = "module_activities"

    id = Column(Integer, primary_key=True, index=True)
    module_id = Column(
        Integer, ForeignKey("learning_modules.id"), nullable=False, index=True
    )
    description = Column(Text, nullable=False)
    order_index = Column(Integer, nullable=False, default=0)
