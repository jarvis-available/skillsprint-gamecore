import re
from typing import List, TypedDict

from app.services.document_parser import ParsedSection


MAX_CHUNK_CHARS = 1200
MIN_CHUNK_CHARS = 200
CHUNK_OVERLAP_SENTENCES = 1


_SENTENCE_END = re.compile(r"(?<=[\.\!\?])\s+(?=[A-Z0-9\"\(])")
_WHITESPACE = re.compile(r"[ \t]+")


class Chunk(TypedDict):
    chunk_code: str
    section_number: str | None
    heading: str | None
    page_number: int | None
    order_index: int
    content: str


def _normalise(text: str) -> str:
    lines = [_WHITESPACE.sub(" ", ln).strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines).strip()


def _split_sentences(paragraph: str) -> List[str]:
    paragraph = paragraph.strip()
    if not paragraph:
        return []
    parts = _SENTENCE_END.split(paragraph)
    return [p.strip() for p in parts if p.strip()]


def _split_paragraphs(text: str) -> List[str]:
    return [p.strip() for p in re.split(r"\n{2,}|\n\s*\n", text) if p.strip()]


def _hard_wrap(text: str, limit: int) -> List[str]:
    if len(text) <= limit:
        return [text]

    out: List[str] = []
    remainder = text
    while len(remainder) > limit:
        cut = remainder.rfind(" ", 0, limit)
        if cut < limit // 2:
            cut = limit
        out.append(remainder[:cut].strip())
        remainder = remainder[cut:].strip()
    if remainder:
        out.append(remainder)
    return [p for p in out if p]


def _pack_sentences(sentences: List[str]) -> List[str]:
    if not sentences:
        return []

    chunks: List[str] = []
    buffer: List[str] = []
    buffer_len = 0

    for sentence in sentences:
        if len(sentence) > MAX_CHUNK_CHARS:
            if buffer:
                chunks.append(" ".join(buffer).strip())
                buffer = []
                buffer_len = 0
            for piece in _hard_wrap(sentence, MAX_CHUNK_CHARS):
                chunks.append(piece)
            continue

        if buffer_len + len(sentence) + 1 <= MAX_CHUNK_CHARS:
            buffer.append(sentence)
            buffer_len += len(sentence) + 1
            continue

        if buffer:
            chunks.append(" ".join(buffer).strip())
        overlap = buffer[-CHUNK_OVERLAP_SENTENCES:] if CHUNK_OVERLAP_SENTENCES > 0 and buffer else []
        buffer = list(overlap) + [sentence]
        buffer_len = sum(len(s) + 1 for s in buffer)

    if buffer:
        chunks.append(" ".join(buffer).strip())

    return [c for c in chunks if c]


def _split_content(content: str) -> List[str]:
    content = _normalise(content)
    if not content:
        return []

    paragraphs = _split_paragraphs(content) or [content]
    sentences: List[str] = []
    for para in paragraphs:
        sentences.extend(_split_sentences(para))

    if not sentences:
        return [content]

    return _pack_sentences(sentences)


def chunk_sections(doc_code: str, sections: List[ParsedSection]) -> List[Chunk]:
    chunks: List[Chunk] = []
    for section in sections:
        content = section["content"]
        if not content or not content.strip():
            continue

        parts = _split_content(content)
        for part_index, part in enumerate(parts):
            if len(part) < MIN_CHUNK_CHARS and chunks:
                previous = chunks[-1]
                merged = previous["content"].rstrip() + " " + part
                if len(merged) <= MAX_CHUNK_CHARS:
                    previous["content"] = merged
                    continue

            section_number = section.get("section_number")
            chunks.append(
                {
                    "chunk_code": f"{doc_code}#pending",
                    "section_number": section_number,
                    "heading": section.get("heading"),
                    "page_number": section.get("page_number"),
                    "order_index": 0,
                    "content": part,
                }
            )

    for idx, c in enumerate(chunks):
        c["order_index"] = idx
        sn = c["section_number"] or f"auto{idx + 1}"
        c["chunk_code"] = f"{doc_code}#{sn}-p{idx + 1}"
    return chunks
