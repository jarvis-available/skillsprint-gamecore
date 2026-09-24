from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin_or_manager
from app.database.connection import get_db
from app.models.user import User
from app.schemas.consistency import ConsistencyRequest, ConsistencyRunOut
from app.services import audit_service, consistency_service


router = APIRouter(prefix="/api/consistency-runs", tags=["consistency"])


def _client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


@router.get("")
def list_runs(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    rows = consistency_service.list_runs(db, skip, limit)
    return {"items": [ConsistencyRunOut.model_validate(r) for r in rows]}


@router.post("", response_model=ConsistencyRunOut, status_code=status.HTTP_201_CREATED)
def create_run(
    payload: ConsistencyRequest,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin_or_manager),
):
    run = consistency_service.run_consistency(
        db,
        employee_user_id=payload.employee_user_id,
        job_role_id=payload.job_role_id,
        max_chunks=payload.max_chunks,
        triggered_by=current.id,
    )
    audit_service.record(
        db,
        current.id,
        "consistency.run",
        "consistency_run",
        run.id,
        details=f"score={run.consistency_score}",
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(run)
    return run


@router.get("/{run_id}", response_model=ConsistencyRunOut)
def get_run(
    run_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return consistency_service.get_run(db, run_id)
