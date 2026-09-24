import csv
import io
from typing import Dict, List


def to_csv(rows: List[Dict], columns: List[str] = None) -> bytes:
    if not rows:
        return b""
    if columns is None:
        columns = list(rows[0].keys())
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        clean = {}
        for c in columns:
            val = row.get(c)
            if val is None:
                clean[c] = ""
            elif isinstance(val, bool):
                clean[c] = "yes" if val else "no"
            else:
                clean[c] = val
        writer.writerow(clean)
    return buf.getvalue().encode("utf-8")


def to_pdf(title: str, rows: List[Dict], columns: List[str] = None) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    if columns is None and rows:
        columns = list(rows[0].keys())
    elif columns is None:
        columns = []

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
    )
    styles = getSampleStyleSheet()
    story = []
    story.append(Paragraph(title, styles["Title"]))
    story.append(Spacer(1, 6 * mm))

    if not rows:
        story.append(Paragraph("No data.", styles["BodyText"]))
    else:
        header = [c.replace("_", " ").title() for c in columns]
        body = []
        for row in rows:
            body_row = []
            for c in columns:
                val = row.get(c, "")
                if val is None:
                    val = ""
                if isinstance(val, bool):
                    val = "yes" if val else "no"
                s = str(val)
                if len(s) > 80:
                    s = s[:77] + "..."
                body_row.append(s)
            body.append(body_row)

        data = [header] + body
        table = Table(data, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 7),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.append(table)

    doc.build(story)
    return buf.getvalue()
