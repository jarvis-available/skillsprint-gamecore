from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.database.connection import Base


class FindingReview(Base):
    __tablename__ = "finding_reviews"

    id = Column(Integer, primary_key=True, index=True)

    finding_id = Column(
        Integer, ForeignKey("validation_findings.id"), nullable=False, index=True
    )
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    decision = Column(String(30), nullable=False, index=True)
    comment = Column(Text, nullable=True)

    override_severity = Column(String(20), nullable=True)
    prior_severity = Column(String(20), nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)


class PlanReview(Base):
    __tablename__ = "plan_reviews"

    id = Column(Integer, primary_key=True, index=True)

    plan_id = Column(
        Integer, ForeignKey("onboarding_plans.id"), nullable=False, index=True
    )
    validation_run_id = Column(
        Integer, ForeignKey("validation_runs.id"), nullable=True
    )
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    decision = Column(String(30), nullable=False, index=True)
    comment = Column(Text, nullable=True)

    prior_status = Column(String(40), nullable=True)
    new_status = Column(String(40), nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
