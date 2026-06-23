from fastapi import APIRouter, Depends

from dependencies import verify_service_secret
from models.internal import CleanupSessionRequest, CleanupSessionResponse
from services import storage
from services.db import user_scoped_tx
from services.embedder import delete_session_chunks

router = APIRouter(
    prefix="/internal", tags=["internal"], dependencies=[Depends(verify_service_secret)]
)


@router.post("/cleanupSession", response_model=CleanupSessionResponse)
async def cleanup_session(body: CleanupSessionRequest) -> CleanupSessionResponse:
    """Called by the hourly Convex expiry cron (ADR-0006). Idempotent —
    re-running on already-clean data is a no-op. Any failure here (Supabase
    Storage included) must surface as a non-200 so Convex leaves the session
    active for the next hourly retry instead of marking it expired."""
    async with user_scoped_tx(body.user_id) as conn:
        await delete_session_chunks(conn, session_id=body.session_id)

    for storage_path in body.storage_paths:
        await storage.delete_pdf(storage_path)

    return CleanupSessionResponse(session_id=body.session_id, deleted=True)
