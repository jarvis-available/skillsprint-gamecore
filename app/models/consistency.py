from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text

from app.database.connection import Base


class ConsistencyRun(Base):
    __tablename__ = "consistency_runs"

    id = Column(Integer, primary_key=True, index=True)

    employee_user_id = Column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    job_role_id = Column(
        Integer, ForeignKey("job_roles.id"), nullable=False, index=True
    )

    plan_a_id = Column(Integer, ForeignKey("onboarding_plans.id"), nullable=True)
    plan_b_id = Column(Integer, ForeignKey("onboarding_plans.id"), nullable=True)

    status = Column(String(30), nullable=False, default="running", index=True)

    consistency_score = Column(Float, nullable=True)
    matched_requirements = Column(Integer, nullable=False, default=0)
    diverged_requirements = Column(Integer, nullable=False, default=0)
    matched_module_categories = Column(Integer, nullable=False, default=0)
    matched_sources = Column(Integer, nullable=False, default=0)
    matched_assessment_topics = Column(Integer, nullable=False, default=0)

    summary_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    triggered_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    finished_at = Column(DateTime, nullable=True)
