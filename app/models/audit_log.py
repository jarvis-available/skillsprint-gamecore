from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.database.connection import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True)
    entity_type = Column(String(50), nullable=True, index=True)
    entity_id = Column(String(50), nullable=True, index=True)

    details = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
