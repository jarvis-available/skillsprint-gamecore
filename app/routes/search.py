from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database.connection import get_db
from app.models.user import User
from app.services import search_service


router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("")
def cross_search(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    q: str = Query(..., min_length=2, max_length=200),
    kinds: Optional[str] = Query(
        default=None,
        description="Comma-separated kinds to include (user,job_role,document,requirement,module,task,plan,quiz,assessment)",
    ),
    limit: int = Query(20, ge=1, le=100),
):
    kind_list: Optional[List[str]] = None
    if kinds:
        kind_list = [k.strip() for k in kinds.split(",") if k.strip()]
    return search_service.cross_entity(db, q, kind_list, limit)
