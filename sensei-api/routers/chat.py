import logging

from fastapi import APIRouter, Depends, HTTPException

from config import get_settings
from dependencies import get_current_user
from models.chat import ChatRequest, ChatResponse
from models.errors import ErrorDetail
from services.convex_client import post_convex
from services.db import user_scoped_tx
from services.embedder import Chunk, store_chunks
from services.encryption import decrypt_key
from services.gemini import ChatHistoryTurn, embed_texts, generate_chat_answer
from utils.scope import MessageScopeResult, check_message_scope, derive_chat_first_scope

router = APIRouter(prefix="/chat", tags=["chat"], dependencies=[Depends(get_current_user)])

logger = logging.getLogger(__name__)

RECENT_MESSAGE_LIMIT = 10
GENERATION_RETRY_ATTEMPTS = 2

NEEDS_TOPIC_MESSAGE = "I'd love to help — what subject or topic are you looking to study today?"


def _error(
    status_code: int, code: str, message: str, detail: dict | None = None
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail=ErrorDetail(code=code, message=message, detail=detail).model_dump(),
    )


def _redirect_message(label: str) -> str:
    return (
        f"That's a little outside what we're studying in this session — **{label}**. "
        f"Let's head back there: what would you like to dig into about {label}? "
        "(And if something else is on your mind that needs real support, please "
        "don't hesitate to reach out to someone who can help.)"
    )


def _new_session_message(label: str) -> str:
    return (
        f"You've asked a few things outside **{label}** now. This session stays "
        f"focused on {label}, but if there's another subject you'd like to study, "
        "you can start a fresh session for it from your dashboard anytime. "
        f"Otherwise — what would you like to explore about {label}?"
    )


async def _persist_turn(
    *,
    session_id: str,
    user_id: str,
    question: str,
    outcome: str,
    assistant_content: str | None = None,
    response_type: str | None = None,
    source: str | None = None,
    refund_allowance: bool = False,
) -> dict:
    payload: dict = {
        "sessionId": session_id,
        "userId": user_id,
        "userMessage": {"content": question},
        "outcome": outcome,
        "refundAllowance": refund_allowance,
    }
    if assistant_content is not None:
        assistant_message: dict = {"content": assistant_content, "responseType": response_type}
        # Convex's v.optional() means the key may be omitted, not that the
        # value may be `null` — verified empirically (ArgumentValidationError).
        if source is not None:
            assistant_message["source"] = source
        payload["assistantMessage"] = assistant_message
    response = await post_convex("/chat/persistTurn", payload)
    response.raise_for_status()
    return response.json()


@router.post("/ask", response_model=ChatResponse)
async def ask(body: ChatRequest, user_id: str = Depends(get_current_user)) -> ChatResponse:
    try:
        return await _ask(body, user_id)
    except HTTPException:
        raise
    except Exception:
        # Any unhandled failure anywhere in the pipeline (scope derivation,
        # the borderline judge, retrieval, Convex round-trips) surfaces as a
        # clean error instead of a raw 500 — verified empirically against
        # the live Gemini free-tier rate limit during Sprint 4 testing.
        logger.warning("chat/ask failed unexpectedly", exc_info=True)
        raise _error(
            502,
            "GENERATION_FAILED",
            "Something went wrong generating a response. Please try asking again.",
        ) from None


async def _ask(body: ChatRequest, user_id: str) -> ChatResponse:
    context_response = await post_convex(
        "/chat/requestContext",
        {
            "userId": user_id,
            "sessionId": body.session_id,
            "recentMessageLimit": RECENT_MESSAGE_LIMIT,
        },
    )
    if context_response.status_code != 200:
        raise _error(404, "SESSION_NOT_FOUND", "Session not found.")
    context = context_response.json()

    if context["rateLimited"]:
        raise _error(
            429,
            "RATE_LIMITED",
            "Too many requests — please slow down.",
            detail={"resets_in_ms": context["resetsInMs"]},
        )
    if context["sessionExpired"]:
        raise _error(
            403,
            "SESSION_EXPIRED",
            "This session has expired and is read-only. Start a new session to continue.",
        )
    if context["ingestInProgress"]:
        raise _error(
            409,
            "INGEST_IN_PROGRESS",
            "A document is still being processed for this session. Please wait until it's ready.",
        )

    key_ciphertext = context["keyCiphertext"]
    is_default_key = key_ciphertext is None
    api_key = get_settings().GEMINI_API_KEY if is_default_key else decrypt_key(key_ciphertext)

    session = context["session"]
    scope_result: MessageScopeResult
    label: str

    if session["scopeSource"] is None:
        # Chat-first, first message: derive scope (un-metered). The first
        # interaction can never be out of scope — it defines scope (ADR-0011).
        chat_first = await derive_chat_first_scope(body.question, api_key=api_key)
        if chat_first.needs_topic:
            await _persist_turn(
                session_id=body.session_id,
                user_id=user_id,
                question=body.question,
                outcome="answered",
                assistant_content=NEEDS_TOPIC_MESSAGE,
                response_type="direct",
                source=None,
            )
            return ChatResponse(
                answer=NEEDS_TOPIC_MESSAGE,
                response_type="direct",
                source=None,
                chunks_used=0,
                out_of_scope=False,
                new_session_required=False,
            )

        lock_response = await post_convex(
            "/sessions/lockScope",
            {
                "sessionId": body.session_id,
                "scope": chat_first.label,
                "scopeDescription": chat_first.description,
                "scopeSource": "first_question",
            },
        )
        lock_response.raise_for_status()

        anchor_embeddings = await embed_texts(
            [chat_first.description or ""], task_type="RETRIEVAL_DOCUMENT", api_key=api_key
        )
        async with user_scoped_tx(user_id) as conn:
            await store_chunks(
                conn,
                user_id=user_id,
                session_id=body.session_id,
                document_id=f"scope-anchor-{body.session_id}",
                chunks=[
                    Chunk(
                        chunk_index=0,
                        page_number=0,
                        content=chat_first.description or "",
                        embedding=anchor_embeddings[0],
                    )
                ],
                book_title=None,
                is_scope_anchor=True,
            )
        await post_convex(
            "/sessions/updateTotals",
            {"sessionId": body.session_id, "chunkDelta": 1, "storageDelta": 0},
        )

        scope_result = MessageScopeResult(in_scope=True, similarity=1.0, used_judge=False)
        label = chat_first.label or ""
    else:
        # Embed once; the same embedding feeds RAG retrieval (ADR-0004).
        question_embeddings = await embed_texts(
            [body.question], task_type="RETRIEVAL_QUERY", api_key=api_key
        )
        async with user_scoped_tx(user_id) as conn:
            scope_result = await check_message_scope(
                conn,
                session_id=body.session_id,
                question=body.question,
                question_embedding=question_embeddings[0],
                ingest_context=session,
                api_key=api_key,
            )
        label = session["scope"] or ""

    if not scope_result.in_scope:
        is_third_strike = session["outOfScopeCount"] >= 2
        message = _new_session_message(label) if is_third_strike else _redirect_message(label)
        outcome = "new_session_prompt" if is_third_strike else "redirect"
        await _persist_turn(
            session_id=body.session_id,
            user_id=user_id,
            question=body.question,
            outcome=outcome,
            assistant_content=message,
            response_type=outcome,
            source=None,
        )
        return ChatResponse(
            answer=message,
            response_type=outcome,
            source=None,
            chunks_used=0,
            out_of_scope=True,
            new_session_required=is_third_strike,
        )

    if is_default_key:
        allowance_response = await post_convex("/chat/consumeAllowance", {"userId": user_id})
        allowance_response.raise_for_status()
        allowance = allowance_response.json()
        if not allowance["allowed"]:
            raise _error(
                429,
                "ALLOWANCE_EXHAUSTED",
                "You've used your free daily allowance. Add your own Gemini key to keep "
                "going, or wait until tomorrow.",
                detail={"resets_at": allowance["resetsAt"]},
            )

    # FOLLOW-UP cap: a count, not a judgment — deterministic from the last
    # assistant message's responseType (ADR-0004).
    recent_messages = context["recentMessages"]
    last_assistant = next((m for m in reversed(recent_messages) if m["role"] == "assistant"), None)
    follow_up = last_assistant is not None and last_assistant["responseType"] == "socratic"

    source_material = (
        "\n\n".join(c.content for c in scope_result.top_chunks) if scope_result.top_chunks else None
    )
    history: list[ChatHistoryTurn] = [
        {"role": m["role"], "content": m["content"]} for m in recent_messages
    ]

    answer_result = None
    for attempt in range(GENERATION_RETRY_ATTEMPTS):
        try:
            answer_result = await generate_chat_answer(
                history=history,
                source_material=source_material,
                question=body.question,
                follow_up=follow_up,
                api_key=api_key,
            )
            break
        except Exception:
            logger.warning("generate_chat_answer failed (attempt %d)", attempt + 1, exc_info=True)
            continue

    if answer_result is None:
        await _persist_turn(
            session_id=body.session_id,
            user_id=user_id,
            question=body.question,
            outcome="failed",
            refund_allowance=is_default_key,
        )
        raise _error(
            502,
            "GENERATION_FAILED",
            "Something went wrong generating a response. Please try asking again.",
        )

    response_type = "direct" if follow_up else answer_result["responseType"]
    source = "general" if source_material is None else answer_result["source"]

    await _persist_turn(
        session_id=body.session_id,
        user_id=user_id,
        question=body.question,
        outcome="answered",
        assistant_content=answer_result["answer"],
        response_type=response_type,
        source=source,
    )

    return ChatResponse(
        answer=answer_result["answer"],
        response_type=response_type,
        source=source,
        chunks_used=len(scope_result.top_chunks),
        out_of_scope=False,
        new_session_required=False,
    )
