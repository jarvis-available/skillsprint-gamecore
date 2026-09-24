from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text

from app.database.connection import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)

    doc_code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    doc_type = Column(String(50), nullable=False, index=True)
    department = Column(String(100), nullable=True, index=True)
    category = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)

    is_active = Column(Boolean, nullable=False, default=True)
    superseded_by_id = Column(Integer, ForeignKey("documents.id"), nullable=True)

    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
