from typing import List, TypedDict

from app.services.document_parser import ParsedSection


MAX_CHUNK_CHARS = 1200
CHUNK_OVERLAP = 150


class Chunk(TypedDict):
    chunk_code: str
    section_number: str | None
    heading: str | None
    page_number: int | None
    order_index: int
    content: str


def _split_long(text: str) -> List[str]:
    if len(text) <= MAX_CHUNK_CHARS:
        return [text]

    parts: List[str] = []
    start = 0
    while start < len(text):
        end = min(start + MAX_CHUNK_CHARS, len(text))
        if end < len(text):
            window = text.rfind(". ", start, end)
            if window > start + MAX_CHUNK_CHARS // 2:
                end = window + 1
            else:
                window = text.rfind(" ", start, end)
                if window > start + MAX_CHUNK_CHARS // 2:
                    end = window
        chunk = text[start:end].strip()
        if chunk:
            parts.append(chunk)
        if end >= len(text):
            break
        start = max(start + 1, end - CHUNK_OVERLAP)
    return parts


def chunk_sections(doc_code: str, sections: List[ParsedSection]) -> List[Chunk]:
    chunks: List[Chunk] = []
    order = 0
    for section in sections:
        content = section["content"].strip()
        if not content:
            continue

        parts = _split_long(content)
        for part_index, part in enumerate(parts):
            sub_suffix = f"-p{part_index + 1}" if len(parts) > 1 else ""
            section_number = section.get("section_number")
            chunk_code = f"{doc_code}#{section_number or f'auto{order + 1}'}{sub_suffix}"
            chunks.append(
                {
                    "chunk_code": chunk_code,
                    "section_number": section_number,
                    "heading": section.get("heading"),
                    "page_number": section.get("page_number"),
                    "order_index": order,
                    "content": part,
                }
            )
            order += 1
    return chunks
