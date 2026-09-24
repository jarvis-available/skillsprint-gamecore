from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.core.constants import DOCUMENT_TYPES


class DocumentBase(BaseModel):
    doc_code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=255)
    doc_type: str
    department: Optional[str] = Field(default=None, max_length=100)
    category: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = None

    @field_validator("doc_type")
    @classmethod
    def _check_doc_type(cls, v: str) -> str:
        if v not in DOCUMENT_TYPES:
            raise ValueError("invalid doc_type")
        return v


class DocumentOut(DocumentBase):
    id: int
    is_active: bool
    superseded_by_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DocumentVersionOut(BaseModel):
    id: int
    document_id: int
    version_number: int
    version_label: Optional[str] = None
    effective_date: Optional[date] = None
    expiry_date: Optional[date] = None
    sha256: str
    mime_type: str
    file_extension: str
    size_bytes: int
    original_filename: str
    is_current: bool
    parse_status: str
    parse_error: Optional[str] = None
    parsed_char_count: Optional[int] = None
    uploaded_at: datetime

    class Config:
        from_attributes = True


class DocumentChunkOut(BaseModel):
    id: int
    document_id: int
    version_id: int
    chunk_code: str
    section_number: Optional[str] = None
    heading: Optional[str] = None
    page_number: Optional[int] = None
    order_index: int
    content: str
    char_count: int
    adversarial_flags: Optional[str] = None

    class Config:
        from_attributes = True


class DocumentDetail(BaseModel):
    document: DocumentOut
    current_version: Optional[DocumentVersionOut] = None
    versions: List[DocumentVersionOut]
