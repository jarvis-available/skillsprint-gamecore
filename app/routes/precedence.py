from typing import Optional

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin
from app.database.connection import get_db
from app.models.user import User
from app.schemas.precedence_rule import (
    PrecedenceRuleCreate,
    PrecedenceRuleOut,
    PrecedenceRuleUpdate,
)
from app.services import audit_service, precedence_rule_service


router = APIRouter(prefix="/api/precedence-rules", tags=["precedence"])


def _client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


@router.get("")
def list_rules(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    include_inactive: bool = False,
):
    rules = precedence_rule_service.list_rules(db, include_inactive)
    return {"items": [PrecedenceRuleOut.model_validate(r) for r in rules]}


@router.post("", response_model=PrecedenceRuleOut, status_code=status.HTTP_201_CREATED)
def create_rule(
    payload: PrecedenceRuleCreate,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin),
):
    rule = precedence_rule_service.create_rule(db, payload)
    audit_service.record(
        db,
        current.id,
        "precedence_rule.create",
        "precedence_rule",
        rule.id,
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(rule)
    return rule


@router.put("/{rule_id}", response_model=PrecedenceRuleOut)
def update_rule(
    rule_id: int,
    payload: PrecedenceRuleUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin),
):
    rule = precedence_rule_service.update_rule(db, rule_id, payload)
    audit_service.record(
        db,
        current.id,
        "precedence_rule.update",
        "precedence_rule",
        rule.id,
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/{rule_id}")
def delete_rule(
    rule_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin),
):
    precedence_rule_service.delete_rule(db, rule_id)
    audit_service.record(
        db,
        current.id,
        "precedence_rule.delete",
        "precedence_rule",
        rule_id,
        ip_address=_client_ip(request),
    )
    db.commit()
    return {"detail": "precedence_rule_deleted"}
