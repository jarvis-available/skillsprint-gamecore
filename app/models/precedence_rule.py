from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, UniqueConstraint

from app.database.connection import Base


class PrecedenceRule(Base):
    __tablename__ = "precedence_rules"
    __table_args__ = (
        UniqueConstraint("source_type", name="uq_precedence_source_type"),
    )

    id = Column(Integer, primary_key=True, index=True)

    source_type = Column(String(50), nullable=False, index=True)
    rank = Column(Integer, nullable=False, default=100)
    label = Column(String(100), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
