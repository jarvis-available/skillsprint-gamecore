from datetime import date
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.constants import DOCUMENT_TYPES
from app.core.deps import get_current_user, require_admin_or_manager
from app.core.exceptions import AppError
from app.database.connection import get_db
from app.models.user import User
from app.schemas.document import (
    DocumentChunkOut,
    DocumentDetail,
    DocumentOut,
    DocumentVersionOut,
)
from app.services import audit_service, document_service


router = APIRouter(prefix="/api/documents", tags=["documents"])


def _client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise AppError("Invalid date format; expected YYYY-MM-DD", 400, "bad_date")


@router.get("")
def list_documents(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: Optional[str] = None,
    doc_type: Optional[str] = None,
    department: Optional[str] = None,
    include_inactive: bool = False,
):
    if doc_type and doc_type not in DOCUMENT_TYPES:
        raise AppError("invalid doc_type filter", 400, "bad_filter")
    items, total = document_service.list_documents(
        db,
        skip=skip,
        limit=limit,
        search=search,
        doc_type=doc_type,
        department=department,
        include_inactive=include_inactive,
    )
    return {
        "total": total,
        "items": [DocumentOut.model_validate(i) for i in items],
    }


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    doc_code: str = Form(...),
    name: str = Form(...),
    doc_type: str = Form(...),
    department: Optional[str] = Form(default=None),
    category: Optional[str] = Form(default=None),
    description: Optional[str] = Form(default=None),
    version_label: Optional[str] = Form(default=None),
    effective_date: Optional[str] = Form(default=None),
    expiry_date: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
    current: User = Depends(require_admin_or_manager),
):
    if doc_type not in DOCUMENT_TYPES:
        raise AppError("invalid doc_type", 400, "bad_doc_type")

    data = await file.read()

    document, version = document_service.upload_document(
        db,
        doc_code=doc_code,
        name=name,
        doc_type=doc_type,
        department=department,
        category=category,
        description=description,
        version_label=version_label,
        effective_date=_parse_date(effective_date),
        expiry_date=_parse_date(expiry_date),
        filename=file.filename or "upload",
        mime_type=file.content_type or "",
        data=data,
        uploaded_by=current.id,
    )

    audit_service.record(
        db,
        current.id,
        "document.upload",
        "document",
        document.id,
        details=f"version={version.version_number}",
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(document)
    db.refresh(version)

    return {
        "document": DocumentOut.model_validate(document),
        "version": DocumentVersionOut.model_validate(version),
    }


@router.get("/{doc_id}", response_model=DocumentDetail)
def get_document(
    doc_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    document = document_service.get_document(db, doc_id)
    current_version = document_service.get_current_version(db, doc_id)
    versions = document_service.list_versions(db, doc_id)
    return DocumentDetail(
        document=DocumentOut.model_validate(document),
        current_version=(
            DocumentVersionOut.model_validate(current_version)
            if current_version
            else None
        ),
        versions=[DocumentVersionOut.model_validate(v) for v in versions],
    )


@router.get("/{doc_id}/chunks")
def list_document_chunks(
    doc_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    version_id: Optional[int] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    document_service.get_document(db, doc_id)
    items, total = document_service.list_chunks(db, doc_id, version_id, skip, limit)
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": [DocumentChunkOut.model_validate(c) for c in items],
    }


@router.get("/versions/{version_id}/download")
def download_version(
    version_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    version = document_service.get_version(db, version_id)
    return Response(
        content=version.file_blob,
        media_type=version.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{version.original_filename}"',
        },
    )


@router.post("/{doc_id}/supersede", response_model=DocumentOut)
def supersede_document(
    doc_id: int,
    request: Request,
    superseded_by_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
    current: User = Depends(require_admin_or_manager),
):
    document = document_service.supersede_document(db, doc_id, superseded_by_id)
    audit_service.record(
        db,
        current.id,
        "document.supersede",
        "document",
        doc_id,
        details=f"superseded_by_id={superseded_by_id}",
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(document)
    return document


@router.post(
    "/versions/{version_id}/make-current", response_model=DocumentVersionOut
)
def make_version_current(
    version_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin_or_manager),
):
    version = document_service.make_version_current(db, version_id)
    audit_service.record(
        db,
        current.id,
        "document.version.make_current",
        "document_version",
        version_id,
        details=f"document_id={version.document_id}",
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(version)
    return version


@router.delete("/{doc_id}")
def deactivate_document(
    doc_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin_or_manager),
):
    document_service.deactivate_document(db, doc_id)
    audit_service.record(
        db,
        current.id,
        "document.deactivate",
        "document",
        doc_id,
        ip_address=_client_ip(request),
    )
    db.commit()
    return {"detail": "document_deactivated"}
