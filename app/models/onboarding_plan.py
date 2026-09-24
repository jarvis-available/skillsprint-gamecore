from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.database.connection import Base


class OnboardingPlan(Base):
    __tablename__ = "onboarding_plans"

    id = Column(Integer, primary_key=True, index=True)

    plan_code = Column(String(50), unique=True, nullable=False, index=True)
    employee_user_id = Column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    job_role_id = Column(
        Integer, ForeignKey("job_roles.id"), nullable=False, index=True
    )

    generation_run_id = Column(
        Integer, ForeignKey("generation_runs.id"), nullable=True
    )

    status = Column(String(30), nullable=False, default="draft", index=True)
    summary_json = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class PlanStage(Base):
    __tablename__ = "plan_stages"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(
        Integer, ForeignKey("onboarding_plans.id"), nullable=False, index=True
    )
    stage = Column(String(30), nullable=False)
    order_index = Column(Integer, nullable=False, default=0)
    description = Column(Text, nullable=True)
