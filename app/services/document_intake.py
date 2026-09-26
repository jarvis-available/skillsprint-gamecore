"""
Document intake helpers: parse-once inspection of an uploaded file to
- reject truly empty documents,
- auto-detect a plausible doc_code, name, doc_type, department, and description,
- flag a mismatch between the admin-declared doc_type and the actual content.

Runs BEFORE the record is persisted. No AI, no side-effects.
"""

from __future__ import annotations

import os
import re
from typing import Dict, List, Optional, TypedDict

from sqlalchemy.orm import Session

from app.core.constants import DOCUMENT_TYPES
from app.core.injection_detector import detect_injection_flags
from app.models.document_chunk import DocumentChunk
from app.models.document_version import DocumentVersion
from app.services import document_parser, similarity_service


MIN_MEANINGFUL_CHARS = 200
CORPUS_RELATEDNESS_MIN = 0.08
CORPUS_SAMPLE_LIMIT = 200
NEAR_DUPLICATE_THRESHOLD = 0.95


class Detection(TypedDict, total=False):
    doc_code: Optional[str]
    name: Optional[str]
    doc_type: Optional[str]
    department: Optional[str]
    description: Optional[str]
    version_label: Optional[str]
    total_chars: int
    section_count: int
    adversarial_hits: int
    type_confidence: float
    type_scores: Dict[str, float]


# ---------------------------------------------------------------------------
# Type keyword profiles - each doc_type has a set of biased words.
# Scored by hit-count normalised by profile size and text length.
# ---------------------------------------------------------------------------
TYPE_KEYWORDS: Dict[str, List[str]] = {
    "handbook": ["handbook", "welcome", "working hours", "dress code", "conduct", "attendance", "onboarding"],
    "hr_policy": ["hr policy", "probation", "confirmation", "grievance", "performance review", "increment", "separation", "recruitment", "payroll"],
    "leave_policy": ["leave", "casual leave", "sick leave", "annual leave", "vacation", "time off", "public holiday"],
    "data_privacy": ["personal data", "consent", "data protection", "retention", "gdpr", "privacy", "customer data", "personally identifiable"],
    "info_security": ["password", "mfa", "phishing", "encryption", "vpn", "malware", "cybersecurity", "information security", "credentials"],
    "workplace_conduct": ["harassment", "conduct", "respect", "diversity", "discrimination", "code of conduct", "ethics", "misconduct"],
    "sop": ["standard operating procedure", "sop", "step", "procedure", "workflow", "checklist", "reception", "escalate"],
    "process_manual": ["process", "workflow", "stages", "approval", "sign-off", "handover", "gate"],
    "role_description": ["role description", "responsibilities", "kpi", "reports to", "competencies", "job description"],
    "faq": ["faq", "frequently asked", "how do i", "how to", "question", "answer"],
    "compliance": ["compliance", "audit", "regulatory", "certification", "iso", "oem standard", "regulation"],
    "safety": ["ppe", "safety", "hazard", "first aid", "fire", "emergency", "evacuation", "protective equipment"],
    "department_guideline": ["department", "guideline", "team standard", "operating norm"],
    "policy": ["policy", "must", "prohibited", "authorised", "shall", "mandatory"],
    "other": [],
}


_WHITESPACE = re.compile(r"\s+")
_DOC_CODE_HINT = re.compile(r"\b([A-Z]{2,6}[-_]?\d{1,4})\b")
_VERSION_HINT = re.compile(r"\b(v(?:er(?:sion)?)?\s*\.?\s*(\d+(?:\.\d+)?))\b", re.IGNORECASE)


def _flatten(sections) -> str:
    parts = []
    for s in sections:
        heading = s.get("heading") or ""
        content = s.get("content") or ""
        if heading:
            parts.append(heading)
        if content:
            parts.append(content)
    return "\n".join(parts)


def _score_type(text_lower: str) -> Dict[str, float]:
    scores: Dict[str, float] = {}
    for dtype, kws in TYPE_KEYWORDS.items():
        if not kws:
            continue
        hits = 0
        for kw in kws:
            if kw in text_lower:
                hits += 1
        # normalise by profile size so short profiles are not penalised
        scores[dtype] = hits / max(1, len(kws))
    return scores


def _guess_department(text_lower: str) -> Optional[str]:
    signals = {
        "Human Resources": ["hr policy", "probation", "grievance", "payroll", "recruitment"],
        "Sales": ["showroom", "walk-in", "test drive", "sales executive", "quotation"],
        "Service": ["service advisor", "job card", "warranty", "workshop reception"],
        "Workshop": ["technician", "bay", "hoist", "coveralls", "ppe"],
        "Finance": ["expense claim", "purchase order", "month-end", "invoice"],
        "Marketing": ["campaign", "brand book", "creative", "social post"],
        "IT": ["dms", "endpoint", "vpn", "cybersecurity"],
        "Quality Assurance": ["pdi", "pre-delivery inspection", "quality control"],
    }
    best_dept, best_score = None, 0
    for dept, kws in signals.items():
        score = sum(1 for kw in kws if kw in text_lower)
        if score > best_score:
            best_score = score
            best_dept = dept
    return best_dept if best_score >= 2 else None


def _extract_doc_code(text: str, filename: Optional[str]) -> Optional[str]:
    if filename:
        base = os.path.splitext(os.path.basename(filename))[0]
        m = _DOC_CODE_HINT.search(base.upper())
        if m:
            return m.group(1).replace("_", "-")
    for line in text.splitlines()[:30]:
        m = _DOC_CODE_HINT.search(line.upper())
        if m:
            return m.group(1).replace("_", "-")
    return None


def _extract_name(sections, filename: Optional[str]) -> Optional[str]:
    for s in sections:
        heading = (s.get("heading") or "").strip()
        if heading and heading.lower() != "table row" and 3 <= len(heading) <= 120:
            return heading
    for s in sections:
        content = (s.get("content") or "").strip()
        if not content:
            continue
        first_line = content.splitlines()[0].strip()
        if 3 <= len(first_line) <= 120:
            return first_line
    if filename:
        base = os.path.splitext(os.path.basename(filename))[0]
        return base.replace("_", " ").replace("-", " ").strip() or None
    return None


def _extract_description(sections) -> Optional[str]:
    for s in sections:
        content = (s.get("content") or "").strip()
        if not content:
            continue
        first = content.split("\n\n", 1)[0]
        first = _WHITESPACE.sub(" ", first).strip()
        if 40 <= len(first) <= 500:
            return first
        if len(first) > 500:
            cut = first[:500].rsplit(" ", 1)[0]
            return cut + "..."
    return None


def _extract_version(text: str) -> Optional[str]:
    m = _VERSION_HINT.search(text)
    if m:
        return f"v{m.group(2)}"
    return None


def inspect(mime_type: str, data: bytes, filename: Optional[str] = None) -> Dict:
    """Parse the file bytes and return an inspection report.
    Never raises for empty content - reports it via total_chars=0 / meaningful=False."""
    try:
        parsed = document_parser.parse(mime_type, data)
    except ValueError as exc:
        return {
            "parseable": False,
            "reason": str(exc),
            "total_chars": 0,
            "meaningful": False,
        }

    sections = parsed["sections"]
    total_chars = parsed["total_chars"]
    joined = _flatten(sections)
    joined_len = len(joined.strip())
    text_lower = joined.lower()

    adversarial_hits = 0
    for s in sections:
        if detect_injection_flags(s.get("content") or ""):
            adversarial_hits += 1

    type_scores = _score_type(text_lower)
    if type_scores:
        best_type = max(type_scores, key=lambda k: type_scores[k])
        best_score = type_scores[best_type]
    else:
        best_type = None
        best_score = 0.0

    detection: Detection = {
        "doc_code": _extract_doc_code(joined, filename),
        "name": _extract_name(sections, filename),
        "doc_type": best_type if best_score > 0 else None,
        "department": _guess_department(text_lower),
        "description": _extract_description(sections),
        "version_label": _extract_version(joined),
        "total_chars": total_chars,
        "section_count": len(sections),
        "adversarial_hits": adversarial_hits,
        "type_confidence": round(best_score, 3),
        "type_scores": {k: round(v, 3) for k, v in type_scores.items() if v > 0},
    }

    return {
        "parseable": True,
        "reason": None,
        "total_chars": total_chars,
        "meaningful": joined_len >= MIN_MEANINGFUL_CHARS,
        "detection": detection,
    }


def validate_declared_type(declared_type: str, detection: Detection) -> Optional[str]:
    """Return a warning string if the declared doc_type does not agree with
    the detected type, or None if they agree well enough.

    Rules:
    - If no keyword hits anywhere, the file is not recognisable as any onboarding
      document (lorem ipsum, random prose, off-topic content) -> reject.
    - If the declared type is present in detection.type_scores with score >= 0.15, accept.
    - Else, return a warning that names the top-detected type.
    """
    if declared_type == "other":
        return None

    scores = detection.get("type_scores") or {}
    if not scores:
        return (
            "The uploaded content does not contain vocabulary typical of any onboarding "
            "document (policy, SOP, FAQ, safety, compliance, role description, handbook, etc.). "
            "Please upload a real company document instead of placeholder or off-topic text."
        )

    declared_score = scores.get(declared_type, 0.0)
    if declared_score >= 0.15:
        return None

    best = detection.get("doc_type")
    if best and best != declared_type:
        return (
            f"The uploaded content looks more like a '{best}' than the declared '{declared_type}'. "
            f"Please reconfirm the doc_type before proceeding, or re-upload with the correct file."
        )
    return (
        f"The uploaded content does not clearly match a '{declared_type}' document. "
        f"Please reconfirm."
    )


def check_corpus_relatedness(db: Session, sample_text: str) -> Optional[dict]:
    """Compare the new document's content against the existing corpus (current
    versions only). If the top similarity is below CORPUS_RELATEDNESS_MIN, return
    a warning dict; otherwise None. If the corpus is empty, skip (return None).

    This catches lorem-ipsum-that-happened-to-match-keywords cases, or wikipedia
    articles about unrelated topics, once at least one real doc is in the system.
    """
    if not sample_text or len(sample_text) < 100:
        return None

    rows = (
        db.query(DocumentChunk.content)
        .join(DocumentVersion, DocumentChunk.version_id == DocumentVersion.id)
        .filter(DocumentVersion.is_current.is_(True))
        .filter(
            (DocumentChunk.adversarial_flags.is_(None))
            | (DocumentChunk.adversarial_flags == "")
        )
        .limit(CORPUS_SAMPLE_LIMIT)
        .all()
    )
    corpus = [r[0] for r in rows if r[0]]
    if not corpus:
        return None

    _, best = similarity_service.max_score_against(sample_text[:4000], corpus)
    if best < CORPUS_RELATEDNESS_MIN:
        return {
            "score": round(best, 4),
            "threshold": CORPUS_RELATEDNESS_MIN,
            "message": (
                "The uploaded content appears unrelated to any document already in the "
                "corpus (top similarity {:.3f} < {:.2f}). This looks like off-topic or "
                "placeholder content. Upload a real company document, or re-upload with "
                "override_type_mismatch=true if you are certain."
            ).format(best, CORPUS_RELATEDNESS_MIN),
        }
    return None


def check_near_duplicate(db: Session, sample_text: str, exclude_document_id: Optional[int] = None) -> Optional[dict]:
    """Reject if the new document's content is near-identical to an existing
    document in the corpus (TF-IDF cosine >= NEAR_DUPLICATE_THRESHOLD).

    Catches the case the user described: same doc re-saved from Word (different
    SHA-256 but effectively identical text).
    """
    if not sample_text or len(sample_text) < 200:
        return None

    from app.models.document import Document as DocumentModel

    q = (
        db.query(DocumentModel.id, DocumentModel.doc_code, DocumentModel.name, DocumentChunk.content)
        .join(DocumentVersion, DocumentVersion.document_id == DocumentModel.id)
        .join(DocumentChunk, DocumentChunk.version_id == DocumentVersion.id)
        .filter(DocumentVersion.is_current.is_(True))
        .filter(DocumentModel.is_active.is_(True))
    )
    if exclude_document_id is not None:
        q = q.filter(DocumentModel.id != exclude_document_id)

    rows = q.limit(4000).all()
    if not rows:
        return None

    per_doc: Dict[int, list] = {}
    per_doc_meta: Dict[int, tuple] = {}
    for doc_id, code, name, content in rows:
        if not content:
            continue
        per_doc.setdefault(doc_id, []).append(content)
        per_doc_meta[doc_id] = (code, name)

    if not per_doc:
        return None

    doc_ids = list(per_doc.keys())
    concatenated = [" ".join(per_doc[d])[:20000] for d in doc_ids]
    scores = similarity_service.cosine_scores(sample_text[:20000], concatenated)
    if not scores:
        return None

    best_idx = int(max(range(len(scores)), key=lambda i: scores[i]))
    best_score = float(scores[best_idx])
    if best_score >= NEAR_DUPLICATE_THRESHOLD:
        doc_id = doc_ids[best_idx]
        code, name = per_doc_meta[doc_id]
        return {
            "score": round(best_score, 4),
            "threshold": NEAR_DUPLICATE_THRESHOLD,
            "match_document_id": doc_id,
            "match_doc_code": code,
            "match_name": name,
            "message": (
                f"This file is nearly identical to an existing document '{code}' "
                f"({name}) with similarity {best_score:.3f}. If this is a new version of "
                f"the same document, supersede or version the existing one instead of "
                f"uploading it as a new document."
            ),
        }
    return None
