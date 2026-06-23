import json
import logging

from fastapi import APIRouter, Depends, HTTPException

from config import get_settings
from dependencies import get_current_user
from models.errors import ErrorDetail
from models.evaluate import (
    FeynmanCriticism,
    FeynmanRequest,
    FeynmanResponse,
    FeynmanScores,
    SuggestionsRequest,
    SuggestionsResponse,
)
from services.convex_client import post_convex
from services.db import user_scoped_tx
from services.encryption import decrypt_key
from services.gemini import ChatHistoryTurn, embed_texts, suggest_concepts
from services.retriever import top_k_chunks
from services.scorer import score_explanation

router = APIRouter(prefix="/evaluate", tags=["evaluate"], dependencies=[Depends(get_current_user)])

logger = logging.getLogger(__name__)

SUGGESTIONS_MESSAGE_LIMIT = 100
FEYNMAN_RAG_TOP_K = 10  # more generous than chat's k=5, per ADR-0007
GENERATION_RETRY_ATTEMPTS = 2


def _error(
    status_code: int, code: str, message: str, detail: dict | None = None
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail=ErrorDetail(code=code, message=message, detail=detail).model_dump(),
    )


async def _get_context(session_id: str, user_id: str, recent_message_limit: int) -> dict:
    response = await post_convex(
        "/chat/requestContext",
        {"userId": user_id, "sessionId": session_id, "recentMessageLimit": recent_message_limit},
    )
    if response.status_code != 200:
        raise _error(404, "SESSION_NOT_FOUND", "Session not found.")
    return response.json()


def _resolve_key(context: dict) -> tuple[str, bool]:
    key_ciphertext = context["keyCiphertext"]
    is_default_key = key_ciphertext is None
    api_key = get_settings().GEMINI_API_KEY if is_default_key else decrypt_key(key_ciphertext)
    return api_key, is_default_key


@router.post("/suggestions", response_model=SuggestionsResponse)
async def suggestions(
    body: SuggestionsRequest, user_id: str = Depends(get_current_user)
) -> SuggestionsResponse:
    try:
        return await _suggestions(body, user_id)
    except HTTPException:
        raise
    except Exception:
        logger.warning("evaluate/suggestions failed unexpectedly", exc_info=True)
        raise _error(
            502,
            "GENERATION_FAILED",
            "Something went wrong generating suggestions. Please try again.",
        ) from None


async def _suggestions(body: SuggestionsRequest, user_id: str) -> SuggestionsResponse:
    context = await _get_context(body.session_id, user_id, SUGGESTIONS_MESSAGE_LIMIT)

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
    # ingestInProgress intentionally ignored — reading the discussion to
    # suggest concepts is harmless during a concurrent upload.

    api_key, _ = _resolve_key(context)

    history: list[ChatHistoryTurn] = [
        {"role": m["role"], "content": m["content"]} for m in context["recentMessages"]
    ]
    # Un-metered (ADR-0001) — a helper, not the graded product. No allowance
    # touch, no persistence: this is a stateless suggestion list.
    return SuggestionsResponse(suggestions=await suggest_concepts(history, api_key=api_key))


async def _persist_feynman(
    *,
    session_id: str,
    user_id: str,
    outcome: str,
    score: dict | None = None,
    refund_allowance: bool = False,
) -> dict:
    payload: dict = {
        "sessionId": session_id,
        "userId": user_id,
        "outcome": outcome,
        "refundAllowance": refund_allowance,
    }
    if score is not None:
        payload["score"] = score
    response = await post_convex("/feynman/persist", payload)
    response.raise_for_status()
    return response.json()


@router.post("/feynman", response_model=FeynmanResponse)
async def feynman(
    body: FeynmanRequest, user_id: str = Depends(get_current_user)
) -> FeynmanResponse:
    try:
        return await _feynman(body, user_id)
    except HTTPException:
        raise
    except Exception:
        logger.warning("evaluate/feynman failed unexpectedly", exc_info=True)
        raise _error(
            502,
            "GENERATION_FAILED",
            "Something went wrong generating a response. Please try asking again.",
        ) from None


async def _feynman(body: FeynmanRequest, user_id: str) -> FeynmanResponse:
    # recentMessageLimit=0 — Feynman doesn't need chat history.
    context = await _get_context(body.session_id, user_id, 0)

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
    # ingestInProgress intentionally ignored (ADR-0005 only names /chat/ask) —
    # scoring against the session's existing scope/chunks is harmless during
    # a concurrent upload.

    api_key, is_default_key = _resolve_key(context)

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

    session = context["session"]
    reference_material: str | None = None
    if session["scopeSource"] == "document":
        # Grading reference retrieved by concept name (not the explanation
        # text), grabbed more generously than chat (ADR-0007).
        concept_embeddings = await embed_texts(
            [body.concept], task_type="RETRIEVAL_QUERY", api_key=api_key
        )
        async with user_scoped_tx(user_id) as conn:
            top_chunks = await top_k_chunks(
                conn,
                session_id=body.session_id,
                query_embedding=concept_embeddings[0],
                k=FEYNMAN_RAG_TOP_K,
                exclude_anchor=True,
            )
        if top_chunks:
            reference_material = "\n\n".join(c.content for c in top_chunks)

    scored = None
    for attempt in range(GENERATION_RETRY_ATTEMPTS):
        try:
            scored = await score_explanation(
                concept=body.concept,
                explanation=body.explanation,
                reference_material=reference_material,
                api_key=api_key,
            )
            break
        except Exception:
            logger.warning("score_explanation failed (attempt %d)", attempt + 1, exc_info=True)
            continue

    if scored is None:
        await _persist_feynman(
            session_id=body.session_id,
            user_id=user_id,
            outcome="failed",
            refund_allowance=is_default_key,
        )
        raise _error(
            502,
            "GENERATION_FAILED",
            "Something went wrong generating a response. Please try asking again.",
        )

    raw = scored.scores
    criticism = FeynmanCriticism(
        clear=raw["clear"]["criticism"],
        concise=raw["concise"]["criticism"],
        concrete=raw["concrete"]["criticism"],
        correct=raw["correct"]["criticism"],
        coherent=raw["coherent"]["criticism"],
        complete=raw["complete"]["criticism"],
        courteous=raw["courteous"]["criticism"],
    )

    await _persist_feynman(
        session_id=body.session_id,
        user_id=user_id,
        outcome="scored",
        score={
            "concept": body.concept,
            "explanation": body.explanation,
            "overallScore": scored.overall_score,
            "scoresClear": raw["clear"]["score"],
            "scoresConcise": raw["concise"]["score"],
            "scoresConcrete": raw["concrete"]["score"],
            "scoresCorrect": raw["correct"]["score"],
            "scoresCoherent": raw["coherent"]["score"],
            "scoresComplete": raw["complete"]["score"],
            "scoresCourteous": raw["courteous"]["score"],
            "criticism": json.dumps(criticism.model_dump()),
            "summary": scored.summary,
        },
    )

    return FeynmanResponse(
        concept=body.concept,
        overall_score=scored.overall_score,
        scores=FeynmanScores(
            clear=raw["clear"]["score"],
            concise=raw["concise"]["score"],
            concrete=raw["concrete"]["score"],
            correct=raw["correct"]["score"],
            coherent=raw["coherent"]["score"],
            complete=raw["complete"]["score"],
            courteous=raw["courteous"]["score"],
        ),
        criticism=criticism,
        summary=scored.summary,
        retry_suggested=scored.retry_suggested,
    )
