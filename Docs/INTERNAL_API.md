# INTERNAL API — Sensei

The service-to-service surface between FastAPI and Convex. The public, browser-facing routes live in `API_CONTRACT.md`; this is their counterpart for the trust boundary described in ADR-0003 (FastAPI → Convex) and ADR-0006 (Convex → FastAPI).

## Auth & transport

- **Every call carries the shared secret `CONVEX_SERVICE_SECRET`** in the `X-Service-Secret` header, verified with a **constant-time** comparison on the receiving side. It lives in both environments (see DEPLOYMENT.md).
- **FastAPI → Convex** calls hit purpose-built HTTP endpoints on the Convex **`.convex.site`** host (ADR-0003). A FastAPI breach can invoke only these endpoints — not arbitrary Convex admin.
- **Convex → FastAPI** (`cleanupSession`) is a public, secret-gated route behind FastAPI's TLS proxy (ADR-0006 — Convex cron is external).
- `userId` / `sessionId` passed by FastAPI are always the **verified** values from the inbound JWT (ADR-0003), never client-supplied raw.

**Idempotency note (MVP):** `cleanupSession` is idempotent (safe to retry). `getRequestContext`, `consumeAllowance`, `persistTurn`, and `persistFeynman` mutate counters/records and are **not** idempotent — FastAPI does **not** auto-retry them (at-most-once); a transient failure surfaces to the user as a normal error. A durable outbox is a post-MVP concern.

---

## FastAPI → Convex

### `getRequestContext`

The per-request **start** call (ADR-0010). One round-trip that does the velocity gate and returns everything FastAPI needs to handle a `/chat/ask` or `/evaluate/feynman` request. Folds in ADR-0001 (velocity), ADR-0002 (key blob), ADR-0003 (`tokensValidAfter`), ADR-0010 (history).

**Request:**
```json
{ "userId": "...", "sessionId": "...", "recentMessageLimit": 20 }
```

**Response 200:**
```json
{
  "keyCiphertext": "…or null",
  "tokensValidAfter": 1749600000000,
  "session": {
    "scope": "French History",
    "scopeDescription": "…or null",
    "scopeSource": "first_question",
    "status": "active",
    "outOfScopeCount": 0,
    "totalChunks": 87
  },
  "recentMessages": [
    { "role": "user", "content": "…" },
    { "role": "assistant", "content": "…", "responseType": "socratic", "source": "rag" }
  ]
}
```
- **Velocity** is checked-and-consumed *first* (fixed window, ADR-0001). Over limit → **429** `{ "error": { "code": "RATE_LIMITED", "detail": { "resets_in_ms": 41000 } } }`. FastAPI maps this to the public velocity 429.
- `keyCiphertext` present → BYOK; null → Default Key.
- FastAPI checks `tokensValidAfter` against the token's `iat` (revocation, ADR-0003) and `session.status` (expiry, ADR-0006) itself.
- `recentMessages` omitted/empty for the Feynman path (FastAPI may pass `recentMessageLimit: 0`).

### `consumeAllowance`

Post-scope, **Default-Key only**, race-free check-and-increment of the Daily Allowance (ADR-0001). FastAPI calls this **only after** the message is confirmed in-scope (ADR-0004) and the key is the Default Key.

**Request:** `{ "userId": "..." }`

**Response 200:**
```json
{ "allowed": true, "count": 7, "resetsAt": 1749700800000 }
```
Exhausted → `{ "allowed": false, "resetsAt": 1749700800000 }` (FastAPI returns the public `ALLOWANCE_EXHAUSTED` 429).

### `persistTurn`

Writes a chat turn atomically (ADR-0010): user message, optional assistant message, the out-of-scope counter, `lastActivityAt`, and an allowance refund on failure (ADR-0001).

**Request:**
```json
{
  "sessionId": "...",
  "userId": "...",
  "userMessage": { "content": "What caused the French Revolution?" },
  "outcome": "answered",
  "assistantMessage": { "content": "…", "responseType": "socratic", "source": "rag" },
  "refundAllowance": false
}
```
- `outcome`: `"answered"` | `"redirect"` | `"new_session_prompt"` | `"failed"`.
- **Counter logic (in the mutation):** `redirect` / `new_session_prompt` → **increment** `outOfScopeCount`; `answered` / `failed` (both in-scope) → **reset** it to 0. FastAPI decides `redirect` vs `new_session_prompt` from the *pre-increment* count returned by `getRequestContext`.
- `assistantMessage` is omitted when `outcome: "failed"` (Gemini returned no usable answer); set `refundAllowance: true` if this request had consumed the allowance.
- Bumps `lastActivityAt = now` (ADR-0006).

**Response 200:** `{ "messageIds": ["...", "..."], "outOfScopeCount": 1 }`

### `persistFeynman`

The Feynman analogue of `persistTurn` (ADR-0010 extension). Writes the score atomically, refunding on a failed eval.

**Request:**
```json
{
  "sessionId": "...",
  "userId": "...",
  "outcome": "scored",
  "score": {
    "concept": "Compound Interest",
    "explanation": "…",
    "overallScore": 76,
    "scoresClear": 80, "scoresConcise": 85, "scoresConcrete": 90,
    "scoresCorrect": 75, "scoresCoherent": 70, "scoresComplete": 55,
    "scoresCourteous": 40,
    "criticism": "{…json…}",
    "summary": "…"
  },
  "refundAllowance": false
}
```
- `outcome`: `"scored"` | `"failed"`. On `"failed"`, omit `score` and set `refundAllowance` as appropriate — no row is written.
- **`attemptNumber` is computed in the mutation** (count of existing attempts for this `sessionId`+`concept`, plus one) to avoid a client/FastAPI race — FastAPI does not pass it.
- `overallScore` is the six-C average FastAPI already computed in code (ADR-0007); Convex stores it verbatim.
- Bumps `lastActivityAt`.

**Response 200:** `{ "scoreId": "...", "attemptNumber": 2 }`

---

## Convex → FastAPI

### `cleanupSession`

Called by the hourly Convex expiry cron (ADR-0006). Public, secret-gated, **idempotent**.

**Request (POST, `X-Service-Secret`):** `{ "sessionId": "..." }`

**Behavior:** delete all of the session's chunks from Supabase pgvector (including the `is_scope_anchor` chunk) and all raw PDFs from Supabase Storage (via `documents.storagePath`). Re-running on already-clean data is a no-op.

**Response 200:** `{ "sessionId": "...", "deleted": true }`

On success Convex sets `session.status: "expired"`; on any non-200 the session stays `active` for the next hourly run to retry (ADR-0006).
