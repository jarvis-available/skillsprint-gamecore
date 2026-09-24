from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)

from app.database.connection import Base


class Assessment(Base):
    __tablename__ = "assessments"

    id = Column(Integer, primary_key=True, index=True)

    plan_id = Column(
        Integer, ForeignKey("onboarding_plans.id"), nullable=False, index=True
    )
    module_id = Column(
        Integer, ForeignKey("learning_modules.id"), nullable=True, index=True
    )

    assessment_type = Column(String(30), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    passing_score = Column(Integer, nullable=False, default=70)

    source_document_id = Column(
        Integer, ForeignKey("documents.id"), nullable=True
    )
    source_section = Column(String(100), nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class AssessmentRubric(Base):
    __tablename__ = "assessment_rubrics"

    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(
        Integer, ForeignKey("assessments.id"), nullable=False, index=True
    )

    criterion = Column(Text, nullable=False)
    weight = Column(Float, nullable=False, default=1.0)
    expected_performance = Column(Text, nullable=True)
    pass_condition = Column(Text, nullable=True)
    order_index = Column(Integer, nullable=False, default=0)
