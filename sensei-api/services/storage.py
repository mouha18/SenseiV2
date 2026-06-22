from supabase import AsyncClient, create_async_client

from config import get_settings

BUCKET = "raw-pdfs"

_client: AsyncClient | None = None


async def _get_client() -> AsyncClient:
    # Narrow Storage credential, not the DB service-role key (ADR-0009).
    global _client
    if _client is None:
        settings = get_settings()
        _client = await create_async_client(settings.SUPABASE_URL, settings.SUPABASE_STORAGE_KEY)
    return _client


def build_storage_path(user_id: str, session_id: str, document_id: str) -> str:
    return f"{user_id}/{session_id}/{document_id}.pdf"


async def upload_pdf(storage_path: str, file_bytes: bytes) -> None:
    client = await _get_client()
    await client.storage.from_(BUCKET).upload(
        storage_path, file_bytes, {"content-type": "application/pdf"}
    )


async def delete_pdf(storage_path: str) -> None:
    client = await _get_client()
    await client.storage.from_(BUCKET).remove([storage_path])
