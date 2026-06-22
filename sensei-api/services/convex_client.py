import httpx

from config import get_settings


async def post_convex(path: str, payload: dict) -> httpx.Response:
    """POST to a service-secret-gated Convex HTTP route (ADR-0003).

    Returns the raw response — callers decide how to handle non-200s, since
    some routes use 404 for "not found" and 400 for validation errors.
    """
    settings = get_settings()
    async with httpx.AsyncClient() as client:
        return await client.post(
            f"{settings.CONVEX_SITE_URL}{path}",
            json=payload,
            headers={"X-Service-Secret": settings.CONVEX_SERVICE_SECRET},
        )
