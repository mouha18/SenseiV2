import logging
import math
import statistics
from dataclasses import dataclass, field

import asyncpg

from config import get_settings
from services import gemini
from services.convex_client import post_convex
from services.embedder import Chunk
from services.retriever import RetrievedChunk, description_anchor_similarity, top_k_chunks

logger = logging.getLogger(__name__)

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

# Per-message gate (ADR-0004 amendment, calibrated on 8 synthetic topics —
# provisional, needs re-tuning on real traffic, distinct from
# DOCUMENT_GATE_THRESHOLD above which gates whole documents, not questions).
# Only an IN threshold remains (2026-06-24 follow-up) — there is no longer
# a free, no-judge auto-reject. A short, context-dependent reply ("I don't
# know", answering the tutor's own question) carries no standalone topical
# signal and was scoring as clear-out, wrongly redirecting legitimate
# conversation. Below this threshold now always goes to the judge, which
# is given recent conversation context instead of just the bare message.
SCOPE_THRESHOLD_DOC_IN = 0.66
SCOPE_THRESHOLD_DESC_IN = 0.63
RAG_TOP_K = 5
CONVERSATION_CONTEXT_TURNS = 4


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
        label = await gemini.derive_doc_scope_label(
            sample_text, api_key=get_settings().GEMINI_API_KEY
        )
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
        [c.content for c in sample],
        task_type="RETRIEVAL_DOCUMENT",
        api_key=get_settings().GEMINI_API_KEY,
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


@dataclass
class MessageScopeResult:
    in_scope: bool
    similarity: float
    used_judge: bool
    top_chunks: list[RetrievedChunk] = field(default_factory=list)


@dataclass
class ChatFirstScopeResult:
    needs_topic: bool
    label: str | None = None
    description: str | None = None


def _format_conversation_context(recent_messages: list[dict]) -> str:
    turns = recent_messages[-CONVERSATION_CONTEXT_TURNS:]
    return "\n".join(
        f"{'Student' if m['role'] == 'user' else 'Sensei'}: {m['content']}" for m in turns
    )


async def check_message_scope(
    conn: asyncpg.Connection,
    *,
    session_id: str,
    question: str,
    question_embedding: list[float],
    ingest_context: dict,
    recent_messages: list[dict],
    api_key: str,
) -> MessageScopeResult:
    """Per-message scope gate (ADR-0004 amendment + 2026-06-24 follow-up):
    a single IN threshold is the fast, free "clearly on-topic" path; below
    it always goes to the un-metered LLM judge, now grounded in recent
    conversation context rather than the bare message alone — a short,
    context-dependent reply ("I don't know", answering the tutor's own
    question) has no standalone topical signal and was false-positiving as
    out-of-scope under the old auto-reject. Doc sessions reuse the RAG
    vector search: top-1 similarity is the gate signal, and the same
    top-k chunks are reused as source material so retrieval isn't
    duplicated for the answer call.
    """
    scope_source = ingest_context.get("scopeSource")
    label = ingest_context.get("scope") or ""

    top_chunks: list[RetrievedChunk] = []
    if scope_source == "document":
        top_chunks = await top_k_chunks(
            conn,
            session_id=session_id,
            query_embedding=question_embedding,
            k=RAG_TOP_K,
            exclude_anchor=True,
        )
        similarity = top_chunks[0].similarity if top_chunks else 0.0
        in_threshold = SCOPE_THRESHOLD_DOC_IN
        topic_context = label + "\n\n" + "\n\n".join(c.content for c in top_chunks)
    else:
        anchor_similarity = await description_anchor_similarity(
            conn, session_id=session_id, query_embedding=question_embedding
        )
        similarity = anchor_similarity if anchor_similarity is not None else 0.0
        in_threshold = SCOPE_THRESHOLD_DESC_IN
        topic_context = f"{label}: {ingest_context.get('scopeDescription') or ''}"

    used_judge = False
    if similarity >= in_threshold:
        in_scope = True
    else:
        used_judge = True
        conversation_context = _format_conversation_context(recent_messages)
        in_scope = await gemini.judge_scope(
            topic_context, conversation_context, question, api_key
        )

    logger.info(
        "scope_decision question=%r similarity=%.4f in_scope=%s used_judge=%s",
        question,
        similarity,
        in_scope,
        used_judge,
    )

    return MessageScopeResult(
        in_scope=in_scope, similarity=similarity, used_judge=used_judge, top_chunks=top_chunks
    )


async def derive_chat_first_scope(question: str, api_key: str) -> ChatFirstScopeResult:
    """Thin wrapper around the chat-first topic-derivation prompt
    (PROMPTS.md §2). The first message of a doc-less session locks the
    description anchor; `needsTopic` is the escape hatch for a topic-free
    message (ADR-0011)."""
    result = await gemini.derive_chat_topic(question, api_key=api_key)
    if result["needsTopic"]:
        return ChatFirstScopeResult(needs_topic=True)
    return ChatFirstScopeResult(
        needs_topic=False, label=result["label"], description=result["description"]
    )
