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


class Quiz(Base):
    __tablename__ = "quizzes"

    id = Column(Integer, primary_key=True, index=True)

    plan_id = Column(
        Integer, ForeignKey("onboarding_plans.id"), nullable=False, index=True
    )
    module_id = Column(
        Integer, ForeignKey("learning_modules.id"), nullable=True, index=True
    )

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    passing_score = Column(Integer, nullable=False, default=70)
    total_points = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"), nullable=False, index=True)

    question_type = Column(String(30), nullable=False)
    prompt_text = Column(Text, nullable=False)
    difficulty = Column(String(20), nullable=True)

    source_document_id = Column(
        Integer, ForeignKey("documents.id"), nullable=True
    )
    source_section = Column(String(100), nullable=True)

    explanation = Column(Text, nullable=True)
    correct_answer_json = Column(Text, nullable=True)
    points = Column(Integer, nullable=False, default=1)
    order_index = Column(Integer, nullable=False, default=0)


class QuizOption(Base):
    __tablename__ = "quiz_options"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(
        Integer, ForeignKey("quiz_questions.id"), nullable=False, index=True
    )

    text = Column(Text, nullable=False)
    is_correct = Column(Boolean, nullable=False, default=False)
    order_index = Column(Integer, nullable=False, default=0)
