import httpx
import jwt
from fastapi import Header, HTTPException

from config import get_settings
from models.errors import ErrorDetail

# Convex Auth's static audience for its own issued JWTs (auth.config.ts applicationID).
CONVEX_AUDIENCE = "convex"


def _unauthorized(message: str) -> HTTPException:
    return HTTPException(
        status_code=401,
        detail=ErrorDetail(code="UNAUTHORIZED", message=message).model_dump(),
    )


_cached_jwk: jwt.PyJWK | None = None


async def _get_signing_key(client: httpx.AsyncClient, *, refresh: bool = False) -> jwt.PyJWK:
    # Convex Auth's JWKS omits "kid", which makes PyJWT's PyJWKClient filter out
    # the key entirely (it requires a kid). Fetch and parse the JWKS directly —
    # there's exactly one signing key for this deployment.
    global _cached_jwk
    if _cached_jwk is None or refresh:
        settings = get_settings()
        response = await client.get(f"{settings.CONVEX_SITE_URL}/.well-known/jwks.json")
        response.raise_for_status()
        _cached_jwk = jwt.PyJWK(response.json()["keys"][0])
    return _cached_jwk


async def get_current_user(authorization: str | None = Header(default=None)) -> str:
    if authorization is None or not authorization.startswith("Bearer "):
        raise _unauthorized("Missing or malformed Authorization header")
    token = authorization.removeprefix("Bearer ").strip()

    settings = get_settings()
    async with httpx.AsyncClient() as client:
        try:
            signing_key = await _get_signing_key(client)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=CONVEX_AUDIENCE,
                issuer=settings.CONVEX_SITE_URL,
            )
        except jwt.PyJWTError as exc:
            raise _unauthorized("Invalid or expired token") from exc

        # Convex Auth's sub claim is "<userId>|<sessionId>" (verified empirically, ADR-0003).
        user_id = claims["sub"].split("|")[0]
        iat_ms = claims["iat"] * 1000

        response = await client.post(
            f"{settings.CONVEX_SITE_URL}/authState",
            json={"userId": user_id},
            headers={"X-Service-Secret": settings.CONVEX_SERVICE_SECRET},
        )

    if response.status_code != 200:
        raise _unauthorized("Could not verify user")

    tokens_valid_after = response.json()["tokensValidAfter"]
    if iat_ms < tokens_valid_after:
        raise _unauthorized("Token has been revoked")

    return user_id
