import hashlib
import os
from datetime import date
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import ALLOWED_EXTENSIONS, ALLOWED_MIME_TYPES
from app.core.exceptions import AppError
from app.core.injection_detector import detect_injection_flags, flags_to_string
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.document_version import DocumentVersion
from app.services import document_chunker, document_intake, document_parser


def _validate_upload(filename: str, mime_type: str, size_bytes: int) -> str:
    if size_bytes <= 0:
        raise AppError("Empty file", 400, "empty_file")

    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if size_bytes > max_bytes:
        raise AppError(
            f"File exceeds {settings.MAX_UPLOAD_MB} MB", 413, "file_too_large"
        )

    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise AppError(
            "Only PDF and DOCX files are accepted", 400, "unsupported_extension"
        )

    if mime_type not in ALLOWED_MIME_TYPES:
        raise AppError(
            "Unsupported mime type; expected PDF or DOCX",
            400,
            "unsupported_mime",
        )

    return ALLOWED_MIME_TYPES[mime_type]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _parse_and_persist_chunks(
    db: Session, document: Document, version: DocumentVersion, data: bytes
) -> None:
    try:
        parsed = document_parser.parse(version.mime_type, data)
    except Exception as exc:
        version.parse_status = "failed"
        version.parse_error = str(exc)[:500]
        db.flush()
        return

    version.parsed_char_count = parsed["total_chars"]
    version.parse_status = "parsed"
    version.parse_error = None

    chunks = document_chunker.chunk_sections(document.doc_code, parsed["sections"])
    for c in chunks:
        flags = detect_injection_flags(c["content"])
        db.add(
            DocumentChunk(
                document_id=document.id,
                version_id=version.id,
                chunk_code=c["chunk_code"],
                section_number=c["section_number"],
                heading=(c["heading"] or "")[:500] or None,
                page_number=c["page_number"],
                order_index=c["order_index"],
                content=c["content"],
                char_count=len(c["content"]),
                adversarial_flags=flags_to_string(flags),
            )
        )
    db.flush()


def upload_document(
    db: Session,
    *,
    doc_code: str,
    name: str,
    doc_type: str,
    department: Optional[str],
    category: Optional[str],
    description: Optional[str],
    version_label: Optional[str],
    effective_date: Optional[date],
    expiry_date: Optional[date],
    filename: str,
    mime_type: str,
    data: bytes,
    uploaded_by: Optional[int],
    override_type_mismatch: bool = False,
) -> Tuple[Document, DocumentVersion]:
    ext = _validate_upload(filename, mime_type, len(data))
    sha = _sha256(data)

    existing_version = (
        db.query(DocumentVersion).filter(DocumentVersion.sha256 == sha).first()
    )
    if existing_version:
        raise AppError(
            "Identical file already uploaded", 409, "duplicate_content"
        )

    inspection = document_intake.inspect(mime_type, data, filename)
    if not inspection.get("parseable"):
        raise AppError(
            f"Could not read text from the file: {inspection.get('reason') or 'unknown parser error'}",
            400,
            "unreadable_file",
        )
    if not inspection.get("meaningful"):
        raise AppError(
            "The uploaded file has no meaningful text content (empty or below minimum length).",
            400,
            "empty_content",
        )

    detection = inspection.get("detection") or {}
    if not override_type_mismatch:
        warning = document_intake.validate_declared_type(doc_type, detection)
        if warning:
            raise AppError(warning, 409, "doc_type_mismatch")

        try:
            parsed_for_check = document_parser.parse(mime_type, data)
            sample = "\n".join(
                (s.get("content") or "") for s in parsed_for_check["sections"]
            )
        except Exception:
            sample = ""

        if sample:
            existing_doc_id = None
            existing_doc = db.query(Document).filter(Document.doc_code == doc_code).first()
            if existing_doc:
                existing_doc_id = existing_doc.id

            dup_warn = document_intake.check_near_duplicate(db, sample, exclude_document_id=existing_doc_id)
            if dup_warn:
                raise AppError(dup_warn["message"], 409, "near_duplicate")

            corpus_warn = document_intake.check_corpus_relatedness(db, sample[:5000])
            if corpus_warn:
                raise AppError(corpus_warn["message"], 409, "corpus_unrelated")

    document = db.query(Document).filter(Document.doc_code == doc_code).first()
    if document is None:
        document = Document(
            doc_code=doc_code.strip(),
            name=name.strip(),
            doc_type=doc_type,
            department=department,
            category=category,
            description=description,
            created_by=uploaded_by,
        )
        db.add(document)
        db.flush()
        version_number = 1
    else:
        latest = (
            db.query(DocumentVersion)
            .filter(DocumentVersion.document_id == document.id)
            .order_by(DocumentVersion.version_number.desc())
            .first()
        )
        version_number = (latest.version_number + 1) if latest else 1

        db.query(DocumentVersion).filter(
            DocumentVersion.document_id == document.id,
            DocumentVersion.is_current.is_(True),
        ).update({"is_current": False})

        document.name = name.strip()
        document.doc_type = doc_type
        document.department = department
        document.category = category
        if description is not None:
            document.description = description
        document.is_active = True
        document.superseded_by_id = None
        db.flush()

    version = DocumentVersion(
        document_id=document.id,
        version_number=version_number,
        version_label=(version_label or f"v{version_number}"),
        effective_date=effective_date,
        expiry_date=expiry_date,
        sha256=sha,
        mime_type=mime_type,
        file_extension=ext,
        size_bytes=len(data),
        original_filename=filename[:255],
        file_blob=data,
        is_current=True,
        parse_status="pending",
        uploaded_by=uploaded_by,
    )
    db.add(version)
    db.flush()

    _parse_and_persist_chunks(db, document, version, data)

    return document, version


def list_documents(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
    doc_type: Optional[str] = None,
    department: Optional[str] = None,
    include_inactive: bool = False,
) -> Tuple[List[Document], int]:
    q = db.query(Document)
    if not include_inactive:
        q = q.filter(Document.is_active.is_(True))
    if doc_type:
        q = q.filter(Document.doc_type == doc_type)
    if department:
        q = q.filter(Document.department == department)
    if search:
        like = f"%{search.strip()}%"
        q = q.filter(
            (Document.name.ilike(like))
            | (Document.doc_code.ilike(like))
            | (Document.description.ilike(like))
        )
    total = q.count()
    items = q.order_by(Document.updated_at.desc()).offset(skip).limit(limit).all()
    return items, total


def get_document(db: Session, doc_id: int) -> Document:
    document = db.query(Document).filter(Document.id == doc_id).first()
    if document is None:
        raise AppError("Document not found", 404, "document_not_found")
    return document


def list_versions(db: Session, doc_id: int) -> List[DocumentVersion]:
    return (
        db.query(DocumentVersion)
        .filter(DocumentVersion.document_id == doc_id)
        .order_by(DocumentVersion.version_number.desc())
        .all()
    )


def get_current_version(db: Session, doc_id: int) -> Optional[DocumentVersion]:
    return (
        db.query(DocumentVersion)
        .filter(
            DocumentVersion.document_id == doc_id,
            DocumentVersion.is_current.is_(True),
        )
        .first()
    )


def get_version(db: Session, version_id: int) -> DocumentVersion:
    v = db.query(DocumentVersion).filter(DocumentVersion.id == version_id).first()
    if v is None:
        raise AppError("Version not found", 404, "version_not_found")
    return v


def list_chunks(
    db: Session,
    doc_id: int,
    version_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
) -> Tuple[List[DocumentChunk], int]:
    q = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc_id)
    if version_id is not None:
        q = q.filter(DocumentChunk.version_id == version_id)
    else:
        current = get_current_version(db, doc_id)
        if current is None:
            return [], 0
        q = q.filter(DocumentChunk.version_id == current.id)
    total = q.count()
    items = (
        q.order_by(DocumentChunk.order_index.asc()).offset(skip).limit(limit).all()
    )
    return items, total


def deactivate_document(db: Session, doc_id: int) -> Document:
    document = get_document(db, doc_id)
    document.is_active = False
    db.flush()
    return document


def make_version_current(db: Session, version_id: int) -> DocumentVersion:
    version = get_version(db, version_id)
    db.query(DocumentVersion).filter(
        DocumentVersion.document_id == version.document_id,
        DocumentVersion.is_current.is_(True),
        DocumentVersion.id != version.id,
    ).update({"is_current": False})
    version.is_current = True
    db.flush()
    return version


def supersede_document(
    db: Session, doc_id: int, superseded_by_id: Optional[int]
) -> Document:
    document = get_document(db, doc_id)

    if superseded_by_id is not None:
        if superseded_by_id == doc_id:
            raise AppError(
                "A document cannot supersede itself", 400, "invalid_supersede"
            )
        target = db.query(Document).filter(Document.id == superseded_by_id).first()
        if target is None:
            raise AppError(
                "Superseding document not found", 404, "supersede_target_not_found"
            )
        document.superseded_by_id = superseded_by_id
        document.is_active = False
    else:
        document.superseded_by_id = None
        document.is_active = True

    db.flush()
    return document
