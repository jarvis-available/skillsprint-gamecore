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


class ValidationRun(Base):
    __tablename__ = "validation_runs"

    id = Column(Integer, primary_key=True, index=True)

    plan_id = Column(
        Integer, ForeignKey("onboarding_plans.id"), nullable=False, index=True
    )

    status = Column(String(30), nullable=False, default="running", index=True)
    final_status = Column(String(40), nullable=True, index=True)

    coverage_score = Column(Float, nullable=True)
    traceability_score = Column(Float, nullable=True)
    requirement_consistency_score = Column(Float, nullable=True)

    mandatory_total = Column(Integer, nullable=False, default=0)
    mandatory_covered = Column(Integer, nullable=False, default=0)
    optional_total = Column(Integer, nullable=False, default=0)
    optional_covered = Column(Integer, nullable=False, default=0)

    missing_requirement_count = Column(Integer, nullable=False, default=0)
    unsupported_requirement_count = Column(Integer, nullable=False, default=0)
    duplicate_count = Column(Integer, nullable=False, default=0)
    contradiction_count = Column(Integer, nullable=False, default=0)
    hallucination_count = Column(Integer, nullable=False, default=0)
    role_irrelevance_count = Column(Integer, nullable=False, default=0)
    sequence_violation_count = Column(Integer, nullable=False, default=0)
    distractor_conflict_count = Column(Integer, nullable=False, default=0)
    outdated_source_count = Column(Integer, nullable=False, default=0)

    summary_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    triggered_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    finished_at = Column(DateTime, nullable=True)


class ValidationFinding(Base):
    __tablename__ = "validation_findings"

    id = Column(Integer, primary_key=True, index=True)

    validation_run_id = Column(
        Integer, ForeignKey("validation_runs.id"), nullable=False, index=True
    )

    entity_type = Column(String(30), nullable=False, index=True)
    entity_id = Column(Integer, nullable=True, index=True)
    entity_code = Column(String(60), nullable=True)

    issue_type = Column(String(40), nullable=False, index=True)
    severity = Column(String(20), nullable=False, default="warning", index=True)

    message = Column(Text, nullable=False)
    expected = Column(Text, nullable=True)
    actual = Column(Text, nullable=True)
    source_reference = Column(String(200), nullable=True)
    score = Column(Float, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class RequirementComparison(Base):
    __tablename__ = "requirement_comparisons"

    id = Column(Integer, primary_key=True, index=True)

    validation_run_id = Column(
        Integer, ForeignKey("validation_runs.id"), nullable=False, index=True
    )
    requirement_id = Column(
        Integer, ForeignKey("requirements.id"), nullable=False, index=True
    )

    python_expected_json = Column(Text, nullable=True)
    genai_result_json = Column(Text, nullable=True)

    coverage_status = Column(String(20), nullable=False, default="missing")
    traceability_status = Column(String(20), nullable=False, default="missing")
    validation_status = Column(String(40), nullable=False, default="requirement_missing")

    matched = Column(Boolean, nullable=False, default=False)
    match_details = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
