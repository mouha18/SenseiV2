from dataclasses import dataclass

import asyncpg


@dataclass
class RetrievedChunk:
    content: str
    page_number: int | None
    book_title: str | None
    chunk_index: int
    similarity: float


async def top_k_chunks(
    conn: asyncpg.Connection,
    *,
    session_id: str,
    query_embedding: list[float],
    k: int,
    exclude_anchor: bool = True,
) -> list[RetrievedChunk]:
    """pgvector cosine search scoped to a session (runs inside the same
    `user_scoped_tx` as other chunk access, ADR-0009 — RLS still applies)."""
    vector_literal = "[" + ",".join(str(v) for v in query_embedding) + "]"
    anchor_clause = "AND is_scope_anchor = false" if exclude_anchor else ""
    rows = await conn.fetch(
        f"""
        SELECT content, page_number, book_title, chunk_index,
               1 - (embedding <=> $1::vector) AS similarity
        FROM chunks
        WHERE session_id = $2
        {anchor_clause}
        ORDER BY embedding <=> $1::vector
        LIMIT $3
        """,
        vector_literal,
        session_id,
        k,
    )
    return [
        RetrievedChunk(
            content=row["content"],
            page_number=row["page_number"],
            book_title=row["book_title"],
            chunk_index=row["chunk_index"],
            similarity=row["similarity"],
        )
        for row in rows
    ]


async def description_anchor_similarity(
    conn: asyncpg.Connection,
    *,
    session_id: str,
    query_embedding: list[float],
) -> float | None:
    """Similarity against the single `is_scope_anchor` chunk that holds a
    doc-less session's embedded scope description (ADR-0004 consequences).
    Returns None if no anchor chunk exists yet."""
    vector_literal = "[" + ",".join(str(v) for v in query_embedding) + "]"
    row = await conn.fetchrow(
        """
        SELECT 1 - (embedding <=> $1::vector) AS similarity
        FROM chunks
        WHERE session_id = $2 AND is_scope_anchor = true
        LIMIT 1
        """,
        vector_literal,
        session_id,
    )
    return row["similarity"] if row else None
