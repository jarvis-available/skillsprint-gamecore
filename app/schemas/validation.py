from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class FindingOut(BaseModel):
    id: int
    entity_type: str
    entity_id: Optional[int] = None
    entity_code: Optional[str] = None
    issue_type: str
    severity: str
    message: str
    expected: Optional[str] = None
    actual: Optional[str] = None
    source_reference: Optional[str] = None
    score: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ComparisonOut(BaseModel):
    id: int
    requirement_id: int
    python_expected_json: Optional[str] = None
    genai_result_json: Optional[str] = None
    coverage_status: str
    traceability_status: str
    validation_status: str
    matched: bool
    match_details: Optional[str] = None

    class Config:
        from_attributes = True


class ValidationRunSummary(BaseModel):
    id: int
    plan_id: int
    status: str
    final_status: Optional[str] = None
    coverage_score: Optional[float] = None
    traceability_score: Optional[float] = None
    mandatory_total: int
    mandatory_covered: int
    missing_requirement_count: int
    unsupported_requirement_count: int
    duplicate_count: int
    contradiction_count: int
    hallucination_count: int
    role_irrelevance_count: int
    sequence_violation_count: int
    distractor_conflict_count: int
    outdated_source_count: int
    error_message: Optional[str] = None
    created_at: datetime
    finished_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ValidationRunDetail(ValidationRunSummary):
    summary_json: Optional[str] = None
    findings: List[FindingOut] = []
    comparisons: List[ComparisonOut] = []
