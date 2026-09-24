from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.database.connection import Base


class PolicyImpact(Base):
    __tablename__ = "policy_impacts"

    id = Column(Integer, primary_key=True, index=True)

    document_id = Column(
        Integer, ForeignKey("documents.id"), nullable=False, index=True
    )
    from_version_id = Column(
        Integer, ForeignKey("document_versions.id"), nullable=True
    )
    to_version_id = Column(
        Integer, ForeignKey("document_versions.id"), nullable=True
    )

    status = Column(String(30), nullable=False, default="analyzed", index=True)

    affected_plan_ids = Column(Text, nullable=True)
    affected_module_ids = Column(Text, nullable=True)
    affected_task_ids = Column(Text, nullable=True)
    affected_quiz_question_ids = Column(Text, nullable=True)
    affected_assessment_ids = Column(Text, nullable=True)
    affected_employee_user_ids = Column(Text, nullable=True)

    summary_json = Column(Text, nullable=True)

    triggered_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
