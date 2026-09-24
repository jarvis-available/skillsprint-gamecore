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
)

from app.database.connection import Base


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id = Column(Integer, primary_key=True, index=True)

    quiz_id = Column(Integer, ForeignKey("quizzes.id"), nullable=False, index=True)
    employee_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    score = Column(Float, nullable=False, default=0.0)
    max_score = Column(Float, nullable=False, default=0.0)
    percentage = Column(Float, nullable=False, default=0.0)
    passed = Column(Boolean, nullable=False, default=False)

    answers_json = Column(Text, nullable=False)
    grading_json = Column(Text, nullable=True)

    submitted_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)


class AssessmentAttempt(Base):
    __tablename__ = "assessment_attempts"

    id = Column(Integer, primary_key=True, index=True)

    assessment_id = Column(
        Integer, ForeignKey("assessments.id"), nullable=False, index=True
    )
    employee_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    total_score = Column(Float, nullable=False, default=0.0)
    max_score = Column(Float, nullable=False, default=0.0)
    percentage = Column(Float, nullable=False, default=0.0)
    passed = Column(Boolean, nullable=False, default=False)

    rubric_scores_json = Column(Text, nullable=False)
    notes = Column(Text, nullable=True)
    graded_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    submitted_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)


class LearningRecommendation(Base):
    __tablename__ = "learning_recommendations"

    id = Column(Integer, primary_key=True, index=True)

    plan_id = Column(
        Integer, ForeignKey("onboarding_plans.id"), nullable=False, index=True
    )
    employee_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    recommendation_type = Column(String(30), nullable=False, index=True)
    reason = Column(Text, nullable=False)

    target_module_id = Column(Integer, ForeignKey("learning_modules.id"), nullable=True)
    target_task_id = Column(Integer, ForeignKey("plan_tasks.id"), nullable=True)
    target_requirement_id = Column(
        Integer, ForeignKey("requirements.id"), nullable=True
    )

    priority = Column(String(20), nullable=False, default="medium")
    status = Column(String(20), nullable=False, default="pending", index=True)
    score = Column(Float, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    resolved_at = Column(DateTime, nullable=True)
