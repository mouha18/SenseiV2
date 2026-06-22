import math
import statistics
from dataclasses import dataclass

import asyncpg

from services import gemini
from services.convex_client import post_convex
from services.embedder import Chunk
from services.retriever import description_anchor_similarity, top_k_chunks

GATE_SAMPLE_SIZE = 10
# Provisional. ADR-0011 seeded this from ADR-0004's doc-mode clear-in edge
# (0.66), but live Sprint 3 testing showed that edge doesn't transfer:
# chunk-vs-chunk (full paragraphs) runs systematically higher than the
# question-vs-anchor distribution ADR-0004 calibrated. One measured pair —
# Photosynthesis chunks vs an unrelated French Revolution chunk — scored
# 0.64-0.67 (clearly off-topic), while a second on-topic Photosynthesis
# chunk scored 0.85 against the same anchor. 0.75 was picked to sit cleanly
# between those two observed clusters; it is still a single-pair anecdote,
# not a calibration, and needs a real `/calibration`-style pass (ADR-0011)
# before launch.
DOCUMENT_GATE_THRESHOLD = 0.75
LABEL_SAMPLE_CHARS = 4000


@dataclass
class GateResult:
    in_scope: bool
    locked_now: bool
    label: str | None = None


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def sample_for_gate(chunks: list[Chunk], n: int = GATE_SAMPLE_SIZE) -> list[Chunk]:
    """Bounded, evenly-spaced sample across the document (ADR-0011) — not
    just the first N, so a document that starts on-topic and drifts doesn't
    pass on a biased sample."""
    if len(chunks) <= n:
        return chunks
    step = len(chunks) / n
    return [chunks[int(i * step)] for i in range(n)]


def median_aggregate(similarities: list[float]) -> float:
    return statistics.median(similarities)


async def _anchor_similarity(
    conn: asyncpg.Connection,
    *,
    session_id: str,
    query_embedding: list[float],
    chunk_anchor: bool,
) -> float:
    if chunk_anchor:
        top = await top_k_chunks(
            conn, session_id=session_id, query_embedding=query_embedding, k=1, exclude_anchor=True
        )
        return top[0].similarity if top else 0.0

    similarity = await description_anchor_similarity(
        conn, session_id=session_id, query_embedding=query_embedding
    )
    return similarity if similarity is not None else 0.0


async def lock_or_gate_document(
    conn: asyncpg.Connection,
    *,
    session_id: str,
    ingest_context: dict,
    chunks: list[Chunk],
) -> GateResult:
    """Upload-first → derive the label and lock scope (first interaction can
    never be out of scope, ADR-0011). Later uploads → gate a bounded sample
    against the locked anchor with a median/quorum aggregate, not top-1
    (ADR-0011) — a document must be on-topic as a body, not by a stray chunk.
    """
    scope_source = ingest_context.get("scopeSource")

    if scope_source is None:
        sample_text = "\n\n".join(c.content for c in chunks)[:LABEL_SAMPLE_CHARS]
        label = await gemini.derive_doc_scope_label(sample_text)
        response = await post_convex(
            "/sessions/lockScope",
            {
                "sessionId": session_id,
                "scope": label,
                "scopeSource": "document",
            },
        )
        response.raise_for_status()
        return GateResult(in_scope=True, locked_now=True, label=label)

    sample = sample_for_gate(chunks)
    sample_embeddings = await gemini.embed_texts(
        [c.content for c in sample], task_type="RETRIEVAL_DOCUMENT"
    )
    chunk_anchor = scope_source == "document"
    similarities = [
        await _anchor_similarity(
            conn, session_id=session_id, query_embedding=emb, chunk_anchor=chunk_anchor
        )
        for emb in sample_embeddings
    ]
    aggregate = median_aggregate(similarities)
    return GateResult(in_scope=aggregate >= DOCUMENT_GATE_THRESHOLD, locked_now=False)
