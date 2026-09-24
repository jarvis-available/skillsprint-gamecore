from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.database.connection import Base


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True)

    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    version_id = Column(
        Integer, ForeignKey("document_versions.id"), nullable=False, index=True
    )

    chunk_code = Column(String(50), nullable=False, index=True)
    section_number = Column(String(50), nullable=True, index=True)
    heading = Column(String(500), nullable=True)
    page_number = Column(Integer, nullable=True)
    order_index = Column(Integer, nullable=False, default=0)

    content = Column(Text, nullable=False)
    char_count = Column(Integer, nullable=False, default=0)

    adversarial_flags = Column(String(255), nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
