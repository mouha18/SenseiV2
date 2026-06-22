import hashlib
import io
import re
from dataclasses import dataclass, field

import asyncpg
from pypdf import PdfReader
from pypdf.errors import PdfReadError

CHUNK_CHARS = 1000
CHUNK_OVERLAP = 150
MIN_EXTRACTED_CHARS = 200
SHINGLE_SIZE = 5
NEAR_DUP_JACCARD = 0.8

_BOILERPLATE_PATTERNS = [
    re.compile(r"^\s*\d+\s*$"),  # bare page numbers
    re.compile(r"^\s*page\s+\d+(\s+of\s+\d+)?\s*$", re.IGNORECASE),
    re.compile(r"^\s*copyright\b.*$", re.IGNORECASE),
    re.compile(r"^\s*all rights reserved\.?\s*$", re.IGNORECASE),
]


class ExtractionFailed(Exception):
    """Raised when a PDF yields negligible text (scanned/image-only, ADR-0005)."""


@dataclass
class Chunk:
    chunk_index: int
    page_number: int
    content: str
    embedding: list[float] = field(default_factory=list)


def extract_pdf_text(file_bytes: bytes) -> list[tuple[int, str]]:
    """Returns (page_number, text) pairs, 1-indexed. Raises ExtractionFailed
    when the PDF is scanned/image-only (negligible extractable text, ADR-0005
    — no OCR for MVP)."""
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
    except PdfReadError as exc:
        raise ExtractionFailed("Couldn't read this PDF — it may be corrupted.") from exc

    pages: list[tuple[int, str]] = []
    total_chars = 0
    for i, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append((i, text))
            total_chars += len(text)

    if total_chars < MIN_EXTRACTED_CHARS:
        raise ExtractionFailed(
            "Couldn't read text from this PDF — scanned or image-only documents "
            "aren't supported yet."
        )
    return pages


def chunk_pages(pages: list[tuple[int, str]]) -> list[Chunk]:
    """Fixed-size chunking with overlap, tracking page_number + chunk_index."""
    chunks: list[Chunk] = []
    index = 0
    for page_number, text in pages:
        start = 0
        while start < len(text):
            end = start + CHUNK_CHARS
            content = text[start:end].strip()
            if content:
                chunks.append(Chunk(chunk_index=index, page_number=page_number, content=content))
                index += 1
            if end >= len(text):
                break
            start = end - CHUNK_OVERLAP
    return chunks


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _shingles(text: str, size: int = SHINGLE_SIZE) -> set[str]:
    words = text.split()
    if len(words) < size:
        return {" ".join(words)}
    return {" ".join(words[i : i + size]) for i in range(len(words) - size + 1)}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def compact_chunks(chunks: list[Chunk]) -> list[Chunk]:
    """Standing ingestion-quality step (ADR-0005): drop exact/near-duplicate
    chunks (text hashing/shingling, no embeddings) and obvious boilerplate.
    Never drops *distinct* content."""
    kept: list[Chunk] = []
    seen_hashes: set[str] = set()
    kept_shingles: list[set[str]] = []

    for chunk in chunks:
        normalized = _normalize(chunk.content)
        if not normalized or len(normalized) < 20:
            continue
        if any(p.match(normalized) for p in _BOILERPLATE_PATTERNS):
            continue

        content_hash = hashlib.sha256(normalized.encode()).hexdigest()
        if content_hash in seen_hashes:
            continue

        shingles = _shingles(normalized)
        if any(_jaccard(shingles, existing) >= NEAR_DUP_JACCARD for existing in kept_shingles):
            continue

        seen_hashes.add(content_hash)
        kept_shingles.append(shingles)
        kept.append(chunk)

    # Re-sequence chunk_index after dropping entries.
    for new_index, chunk in enumerate(kept):
        chunk.chunk_index = new_index
    return kept


async def delete_document_chunks(conn: asyncpg.Connection, *, document_id: str) -> None:
    await conn.execute("DELETE FROM chunks WHERE document_id = $1", document_id)


async def store_chunks(
    conn: asyncpg.Connection,
    *,
    user_id: str,
    session_id: str,
    document_id: str,
    chunks: list[Chunk],
    book_title: str | None,
    is_scope_anchor: bool = False,
) -> None:
    for chunk in chunks:
        vector_literal = "[" + ",".join(str(v) for v in chunk.embedding) + "]"
        await conn.execute(
            """
            INSERT INTO chunks
                (user_id, session_id, document_id, content, embedding,
                 page_number, book_title, chunk_index, is_scope_anchor)
            VALUES ($1, $2, $3, $4, $5::vector, $6, $7, $8, $9)
            """,
            user_id,
            session_id,
            document_id,
            chunk.content,
            vector_literal,
            chunk.page_number,
            book_title,
            chunk.chunk_index,
            is_scope_anchor,
        )
