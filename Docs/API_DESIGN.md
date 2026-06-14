# API DESIGN — Sensei

**Base URL:** `http://localhost:8000` (dev) / `https://api.sensei.app` (prod)
**Protocol:** HTTPS
**Auth:** Convex session token passed in `Authorization` header
**Format:** JSON (request and response)
**Version:** v1 (no prefix for MVP — add `/v1/` prefix before going multi-version)

---

## Design Principles

1. Resource-oriented URLs — nouns, not verbs (`/chat/ask` not `/doChat`)
2. HTTP verbs carry the action — POST for AI operations, GET for reads
3. Every route requires auth except `/health`
4. Thin routers — routes delegate immediately to services, no logic in route handlers
5. Consistent error shape across all endpoints
6. Rate limited per user per minute on all AI routes

---

## Authentication

Every request to a protected route must include:

```text
Authorization: Bearer <convex_session_token>
```

FastAPI verifies this token **offline** against Convex's published JWKS via `Depends(get_current_user)` — no per-request call to Convex — and rejects tokens issued before the user's `tokensValidAfter` (logout/revoke). See ADR-0003. Invalid or missing token returns `401`.

**Public routes (no auth required):**
- `GET /health`

---

## Resource Map

### Health

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| GET | `/health` | API health check | No |

### Ingest

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| POST | `/ingest/upload` | Upload a PDF; processes into chunks asynchronously | Yes |
| POST | `/ingest/cancel` | Cancel an in-progress upload | Yes |

### Chat

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| POST | `/chat/ask` | Send a question, receive a Socratic or direct answer | Yes |

### Evaluate

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| POST | `/evaluate/feynman` | Submit a concept explanation for 7C's scoring | Yes |

---

## Error Responses

All errors follow this shape:

```json
{
  "error": {
    "code": "OUT_OF_SCOPE",
    "message": "This question is outside the session topic. We're focusing on French History.",
    "detail": null
  }
}
```

| Code | HTTP Status | Meaning |
|---|---|---|
| `UNAUTHORIZED` | 401 | Missing or invalid Convex token |
| `FORBIDDEN` | 403 | Token valid but user doesn't own this session |
| `VALIDATION_ERROR` | 422 | Request body failed Pydantic validation |
| `RATE_LIMITED` | 429 | More than 20 requests per minute |
| `STORAGE_LIMIT` | 400 | Upload exceeds 5MB per file or 20MB per session |
| `CHUNK_LIMIT` | 400 | Session already has 200 chunks |
| `INGEST_IN_PROGRESS` | 409 | A document in this session is still processing |
| `DOCUMENT_NOT_FOUND` | 404 | No in-progress document with that ID (cancel) |
| `SESSION_EXPIRED` | 403 | Session expired — read-only (ADR-0006) |
| `ALLOWANCE_EXHAUSTED` | 429 | Daily Allowance used — add a key or wait (ADR-0001) |
| `OUT_OF_SCOPE` | 200 | Question outside session scope (not an error, handled gracefully) |
| `NEW_SESSION_REQUIRED` | 200 | 3 consecutive out-of-scope messages — prompt to start new session |
| `GEMINI_ERROR` | 502 | Gemini API call failed (bad key, quota exceeded, etc.) |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

---

## Rate Limiting

| Route category | Limit |
|---|---|
| `/chat/ask` | 20 requests / minute / user |
| `/evaluate/feynman` | 20 requests / minute / user |
| `/ingest/upload` | 10 requests / minute / user |
| `/health` | Unlimited |

Headers returned on rate-limited responses:
```text
X-RateLimit-Limit: 20
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1234567890
```
