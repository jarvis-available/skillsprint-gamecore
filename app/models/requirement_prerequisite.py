from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, UniqueConstraint

from app.database.connection import Base


class RequirementPrerequisite(Base):
    __tablename__ = "requirement_prerequisites"
    __table_args__ = (
        UniqueConstraint(
            "requirement_id", "prerequisite_id", name="uq_req_prereq"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    requirement_id = Column(
        Integer, ForeignKey("requirements.id"), nullable=False, index=True
    )
    prerequisite_id = Column(
        Integer, ForeignKey("requirements.id"), nullable=False, index=True
    )

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
