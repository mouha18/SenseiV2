import asyncio
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile

from config import get_settings
from dependencies import get_current_user
from models.errors import ErrorDetail
from models.ingest import CancelRequest, CancelResponse, UploadResponse
from services import storage
from services.convex_client import post_convex
from services.db import user_scoped_tx
from services.embedder import (
    Chunk,
    ExtractionFailed,
    chunk_pages,
    compact_chunks,
    delete_document_chunks,
    extract_pdf_text,
    store_chunks,
)
from services.gemini import embed_texts
from utils.scope import GateResult, lock_or_gate_document

router = APIRouter(prefix="/ingest", tags=["ingest"], dependencies=[Depends(get_current_user)])

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_SESSION_BYTES = 20 * 1024 * 1024
MAX_SESSION_CHUNKS = 200
EMBED_BATCH_SIZE = 50

# Cooperative cancellation signals (ADR-0005) — in-process only; an instance
# restart loses in-flight jobs, same caveat as BackgroundTasks itself.
_cancel_events: dict[str, asyncio.Event] = {}


def _error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code, detail=ErrorDetail(code=code, message=message).model_dump()
    )


async def _get_ingest_context(session_id: str) -> dict:
    response = await post_convex("/sessions/ingestContext", {"sessionId": session_id})
    if response.status_code != 200:
        raise _error(404, "SESSION_NOT_FOUND", "Session not found.")
    return response.json()


async def _update_document_status(
    document_id: str, status: str, *, chunk_count: int | None = None, error: str | None = None
) -> None:
    payload: dict = {"documentId": document_id, "status": status}
    if chunk_count is not None:
        payload["chunkCount"] = chunk_count
    if error is not None:
        payload["error"] = error
    await post_convex("/documents/updateStatus", payload)


@router.post("/upload", response_model=UploadResponse)
async def upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session_id: str = Form(...),
    user_id: str = Depends(get_current_user),
) -> UploadResponse:
    content = await file.read()
    if len(content) > MAX_FILE_BYTES:
        raise _error(400, "STORAGE_LIMIT", "File exceeds the 5MB per-file limit.")

    context = await _get_ingest_context(session_id)
    if context["totalStorageBytes"] + len(content) > MAX_SESSION_BYTES:
        raise _error(400, "STORAGE_LIMIT", "Session storage limit of 20MB reached.")
    if context["totalChunks"] >= MAX_SESSION_CHUNKS:
        raise _error(400, "STORAGE_LIMIT", "Session has reached the 200-chunk limit.")

    storage_path = storage.build_storage_path(user_id, session_id, str(uuid.uuid4()))
    await storage.upload_pdf(storage_path, content)

    create_response = await post_convex(
        "/documents/create",
        {
            "sessionId": session_id,
            "userId": user_id,
            "fileName": file.filename or "document.pdf",
            "fileSizeBytes": len(content),
            "storagePath": storage_path,
        },
    )
    if create_response.status_code != 200:
        await storage.delete_pdf(storage_path)
        raise _error(400, "INGEST_FAILED", "Could not start ingestion for this document.")
    document_id = create_response.json()["documentId"]

    background_tasks.add_task(
        _process_document,
        document_id=document_id,
        session_id=session_id,
        user_id=user_id,
        file_bytes=content,
        file_name=file.filename or "document.pdf",
        storage_path=storage_path,
    )

    return UploadResponse(
        status="processing",
        document_id=document_id,
        session_id=session_id,
        file_name=file.filename or "document.pdf",
        file_size_bytes=len(content),
        estimated_chunks=max(1, len(content) // 50_000),
    )


@router.post("/cancel", response_model=CancelResponse)
async def cancel(body: CancelRequest, user_id: str = Depends(get_current_user)) -> CancelResponse:
    _cancel_events.setdefault(body.document_id, asyncio.Event()).set()
    return CancelResponse(document_id=body.document_id, status="cancelled")


async def _process_document(
    *,
    document_id: str,
    session_id: str,
    user_id: str,
    file_bytes: bytes,
    file_name: str,
    storage_path: str,
) -> None:
    cancel_event = _cancel_events.setdefault(document_id, asyncio.Event())
    try:
        try:
            pages = extract_pdf_text(file_bytes)
        except ExtractionFailed as exc:
            await _update_document_status(document_id, "failed", error=str(exc))
            await storage.delete_pdf(storage_path)
            return

        chunks = compact_chunks(chunk_pages(pages))

        if cancel_event.is_set():
            await _update_document_status(document_id, "cancelled")
            await storage.delete_pdf(storage_path)
            return

        context = await _get_ingest_context(session_id)
        if context["totalChunks"] + len(chunks) > MAX_SESSION_CHUNKS:
            await _update_document_status(
                document_id,
                "failed",
                error=(
                    "This document exceeds the 200-chunk session limit; "
                    "upload a smaller excerpt or split it."
                ),
            )
            await storage.delete_pdf(storage_path)
            return

        async with user_scoped_tx(user_id) as conn:
            gate: GateResult = await lock_or_gate_document(
                conn, session_id=session_id, ingest_context=context, chunks=chunks
            )

        if not gate.in_scope:
            label = context.get("scope") or "this session's topic"
            await _update_document_status(
                document_id,
                "rejected",
                error=f"{file_name} looks like it's about something other than {label}.",
            )
            await storage.delete_pdf(storage_path)
            return

        chunks_stored = 0
        for start in range(0, len(chunks), EMBED_BATCH_SIZE):
            if cancel_event.is_set():
                async with user_scoped_tx(user_id) as conn:
                    await delete_document_chunks(conn, document_id=document_id)
                await _update_document_status(document_id, "cancelled")
                await storage.delete_pdf(storage_path)
                return

            batch: list[Chunk] = chunks[start : start + EMBED_BATCH_SIZE]
            embeddings = await embed_texts(
                [c.content for c in batch],
                task_type="RETRIEVAL_DOCUMENT",
                api_key=get_settings().GEMINI_API_KEY,
            )
            for chunk, embedding in zip(batch, embeddings, strict=True):
                chunk.embedding = embedding

            async with user_scoped_tx(user_id) as conn:
                await store_chunks(
                    conn,
                    user_id=user_id,
                    session_id=session_id,
                    document_id=document_id,
                    chunks=batch,
                    book_title=file_name,
                )
            chunks_stored += len(batch)

        await _update_document_status(document_id, "ready", chunk_count=chunks_stored)
        await post_convex(
            "/sessions/updateTotals",
            {
                "sessionId": session_id,
                "chunkDelta": chunks_stored,
                "storageDelta": len(file_bytes),
            },
        )
    finally:
        _cancel_events.pop(document_id, None)
