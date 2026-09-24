from typing import List

from sqlalchemy.orm import Session

from app.core.constants import DEFAULT_PRECEDENCE_ORDER
from app.core.exceptions import AppError
from app.models.precedence_rule import PrecedenceRule
from app.schemas.precedence_rule import PrecedenceRuleCreate, PrecedenceRuleUpdate


def ensure_defaults(db: Session) -> None:
    existing = {r.source_type for r in db.query(PrecedenceRule).all()}
    changed = False
    for rank, source_type in enumerate(DEFAULT_PRECEDENCE_ORDER, start=1):
        if source_type in existing:
            continue
        db.add(
            PrecedenceRule(
                source_type=source_type,
                rank=rank * 10,
                label=source_type.replace("_", " ").title(),
            )
        )
        changed = True
    if changed:
        db.flush()


def list_rules(db: Session, include_inactive: bool = False) -> List[PrecedenceRule]:
    q = db.query(PrecedenceRule)
    if not include_inactive:
        q = q.filter(PrecedenceRule.is_active.is_(True))
    return q.order_by(PrecedenceRule.rank.asc()).all()


def create_rule(db: Session, data: PrecedenceRuleCreate) -> PrecedenceRule:
    if (
        db.query(PrecedenceRule)
        .filter(PrecedenceRule.source_type == data.source_type)
        .first()
    ):
        raise AppError(
            "Precedence rule already exists for this source_type",
            409,
            "precedence_rule_exists",
        )
    rule = PrecedenceRule(
        source_type=data.source_type,
        rank=data.rank,
        label=data.label,
    )
    db.add(rule)
    db.flush()
    return rule


def update_rule(db: Session, rule_id: int, data: PrecedenceRuleUpdate) -> PrecedenceRule:
    rule = db.query(PrecedenceRule).filter(PrecedenceRule.id == rule_id).first()
    if rule is None:
        raise AppError("Precedence rule not found", 404, "precedence_rule_not_found")
    payload = data.model_dump(exclude_unset=True)
    for k, v in payload.items():
        setattr(rule, k, v)
    db.flush()
    return rule


def delete_rule(db: Session, rule_id: int) -> None:
    rule = db.query(PrecedenceRule).filter(PrecedenceRule.id == rule_id).first()
    if rule is None:
        raise AppError("Precedence rule not found", 404, "precedence_rule_not_found")
    db.delete(rule)
    db.flush()
