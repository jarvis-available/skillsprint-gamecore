from typing import Optional

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin_or_manager
from app.core.exceptions import AppError
from app.database.connection import get_db
from app.models.user import User
from app.services import export_service, report_service


router = APIRouter(prefix="/api/reports", tags=["reports"])


REPORT_TITLES = {
    "employee_progress": "Employee Progress Report",
    "role_coverage": "Role Coverage Report",
    "mandatory_training": "Mandatory Training Report",
    "assessment_results": "Assessment Results Report",
    "source_traceability": "Source Traceability Report",
    "hallucination_flags": "Hallucination Flags Report",
    "policy_coverage": "Policy Coverage Report",
    "genai_python_comparison": "GenAI vs Python Comparison Report",
}


def _fetch(db: Session, kind: str, employee_user_id: Optional[int]) -> list:
    kwargs = {}
    if employee_user_id is not None and kind == "employee_progress":
        kwargs["employee_user_id"] = employee_user_id
    return report_service.build_report(db, kind, **kwargs)


@router.get("")
def list_kinds(_: User = Depends(get_current_user)):
    return {
        "kinds": [
            {"key": k, "title": REPORT_TITLES.get(k, k)}
            for k in report_service.REPORT_KINDS
        ]
    }


@router.get("/{kind}")
def get_report(
    kind: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_or_manager),
    employee_user_id: Optional[int] = Query(default=None),
    export: Optional[str] = Query(default=None, pattern="^(csv|pdf)$"),
):
    if kind not in report_service.REPORT_KINDS:
        raise AppError(f"Unknown report kind: {kind}", 400, "unknown_report_kind")

    rows = _fetch(db, kind, employee_user_id)
    title = REPORT_TITLES.get(kind, kind)

    if export == "csv":
        data = export_service.to_csv(rows)
        return Response(
            content=data,
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{kind}.csv"',
            },
        )
    if export == "pdf":
        data = export_service.to_pdf(title, rows)
        return Response(
            content=data,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{kind}.pdf"',
            },
        )

    return {"kind": kind, "title": title, "count": len(rows), "rows": rows}
