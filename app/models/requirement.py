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


class Requirement(Base):
    __tablename__ = "requirements"

    id = Column(Integer, primary_key=True, index=True)

    req_code = Column(String(50), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    requirement_type = Column(String(30), nullable=False, index=True)
    must_type = Column(String(30), nullable=False, index=True)
    priority = Column(String(20), nullable=False, default="medium")
    due_stage = Column(String(30), nullable=True)

    competency = Column(String(255), nullable=True)
    assessment_topic = Column(String(255), nullable=True)

    source_document_id = Column(
        Integer, ForeignKey("documents.id"), nullable=True, index=True
    )
    source_version_id = Column(
        Integer, ForeignKey("document_versions.id"), nullable=True
    )
    source_chunk_id = Column(
        Integer, ForeignKey("document_chunks.id"), nullable=True, index=True
    )
    source_section = Column(String(100), nullable=True)

    is_active = Column(Boolean, nullable=False, default=True)

    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
