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
from sqlalchemy.dialects.mysql import LONGTEXT

from app.database.connection import Base


class GenerationRun(Base):
    __tablename__ = "generation_runs"

    id = Column(Integer, primary_key=True, index=True)

    plan_id = Column(
        Integer, ForeignKey("onboarding_plans.id"), nullable=True, index=True
    )

    prompt_template_id = Column(
        Integer, ForeignKey("prompt_templates.id"), nullable=True
    )
    prompt_version_id = Column(
        Integer, ForeignKey("prompt_versions.id"), nullable=True
    )
    prompt_snapshot = Column(Text().with_variant(LONGTEXT(), "mysql"), nullable=True)

    provider = Column(String(30), nullable=False, default="gemini")
    model_name = Column(String(100), nullable=False)

    input_summary = Column(Text, nullable=True)
    source_document_ids = Column(String(500), nullable=True)
    source_versions_json = Column(Text, nullable=True)

    output_raw = Column(Text().with_variant(LONGTEXT(), "mysql"), nullable=True)
    output_parsed_json = Column(Text().with_variant(LONGTEXT(), "mysql"), nullable=True)

    parsed_ok = Column(Boolean, nullable=False, default=False)
    parse_error = Column(Text, nullable=True)
    retries = Column(Integer, nullable=False, default=0)
    latency_ms = Column(Integer, nullable=True)
    token_estimate = Column(Integer, nullable=True)

    status = Column(String(30), nullable=False, default="running", index=True)

    triggered_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
