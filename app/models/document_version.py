from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
)
from sqlalchemy.dialects.mysql import LONGBLOB

from app.database.connection import Base


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id = Column(Integer, primary_key=True, index=True)

    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)

    version_number = Column(Integer, nullable=False)
    version_label = Column(String(50), nullable=True)

    effective_date = Column(Date, nullable=True)
    expiry_date = Column(Date, nullable=True)

    sha256 = Column(String(64), nullable=False, unique=True, index=True)
    mime_type = Column(String(100), nullable=False)
    file_extension = Column(String(10), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    original_filename = Column(String(255), nullable=False)

    file_blob = Column(LargeBinary().with_variant(LONGBLOB, "mysql"), nullable=False)

    is_current = Column(Boolean, nullable=False, default=True, index=True)

    parsed_char_count = Column(Integer, nullable=True)
    parse_status = Column(String(20), nullable=False, default="pending")
    parse_error = Column(String(500), nullable=True)

    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    uploaded_at = Column(DateTime, nullable=False, default=datetime.utcnow)
