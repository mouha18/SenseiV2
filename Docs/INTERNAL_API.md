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

The per-request **start** call (ADR-0010). One round-trip that does the velocity gate and returns everything FastAPI needs to handle a `/chat/ask` or `/evaluate/feynman` request. Folds in ADR-0001 (velocity), ADR-0002 (key blob), ADR-0005 (ingest-in-progress), ADR-0006 (expiry), ADR-0010 (history). Note: `tokensValidAfter`/revocation is **not** re-checked here — `get_current_user` (ADR-0003) already verified the token via `/authState` before this call is ever made.

**Request:**
```json
{ "userId": "...", "sessionId": "...", "recentMessageLimit": 10 }
```

**Response 200 — normal case:**
```json
{
  "rateLimited": false,
  "sessionExpired": false,
  "ingestInProgress": false,
  "keyCiphertext": "…or null",
  "session": {
    "scope": "French History",
    "scopeDescription": "…or null",
    "scopeSource": "first_question",
    "outOfScopeCount": 0,
    "totalChunks": 87
  },
  "recentMessages": [
    { "role": "user", "content": "…", "responseType": null, "source": null },
    { "role": "assistant", "content": "…", "responseType": "socratic", "source": "rag" }
  ]
}
```
This is a **tagged result, not a thrown error** — `rateLimited`/`sessionExpired`/`ingestInProgress` are expected outcomes the mutation still returns 200 for; only a missing/mismatched user or session throws (mapped to **404** by the HTTP route). FastAPI checks the tags **in order** and maps each to its public response:
- `rateLimited: true` → **429** `{ "error": { "code": "RATE_LIMITED", "detail": { "resets_in_ms": 41000 } } }`. Velocity is checked-and-consumed *first* (fixed 60s window, ADR-0001), before any other field is computed.
- `sessionExpired: true` → **403** `SESSION_EXPIRED` (ADR-0006).
- `ingestInProgress: true` → **409** `INGEST_IN_PROGRESS` (a `documents` row for this session has `status: "processing"`, ADR-0005).
- Otherwise the full context above is present. `keyCiphertext` present → BYOK; `null` → Default Key. `recentMessages` is oldest→newest, already truncated to `recentMessageLimit` (FastAPI passes `0` for the Feynman path, `10` for chat — matching `PROMPTS.md` §1's history window).

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

**Route:** `POST /feynman/persist`. The Feynman analogue of `persistTurn` (ADR-0010 extension). Writes the score atomically, refunding on a failed eval. `getRequestContext`/`consumeAllowance` (above) are reused as-is for the Feynman path — both are already generic, not chat-specific (FastAPI calls `getRequestContext` with `recentMessageLimit: 0`, since Feynman doesn't need chat history).

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

**Response 200:** `{ "scoreId": "...", "attemptNumber": 2 }` (both `null` when `outcome: "failed"`).

### Ingestion endpoints (Sprint 3, ADR-0005/ADR-0011)

FastAPI never writes Convex directly (ADR-0003/0010); these are the only routes that create/update `documents` or touch a session's scope/storage totals during ingestion.

#### `sessions/ingestContext`

**Request:** `{ "sessionId": "..." }`

**Response 200:**
```json
{
  "scope": "French History or null",
  "scopeDescription": "...or null",
  "scopeSource": "document | first_question | null",
  "status": "active",
  "totalChunks": 87,
  "totalStorageBytes": 4200000
}
```
404 if the session doesn't exist. FastAPI uses this to check the 20MB/200-chunk caps and whether scope is already locked before deciding derive vs gate (ADR-0011).

#### `sessions/lockScope`

**Request:** `{ "sessionId": "...", "scope": "...", "scopeDescription": "...optional...", "scopeSource": "document" }`

**Response 200:** `{ "locked": true }`. **400** if the session doesn't exist or scope is already locked — the lock is one-way and irreversible for the session's life (ADR-0011); FastAPI must not call this more than once per session.

#### `sessions/updateTotals`

**Request:** `{ "sessionId": "...", "chunkDelta": 42, "storageDelta": 4200000 }`

**Response 200:** `{ "updated": true }`. Called after a document finishes ingestion (success) or is cleaned up (cancelled/rejected, with negative deltas).

#### `documents/create`

**Request:** `{ "sessionId": "...", "userId": "...", "fileName": "...", "fileSizeBytes": 4200000, "storagePath": "..." }`

**Response 200:** `{ "documentId": "..." }`. Row is created with `status: "processing"`, `chunkCount: 0`.

#### `documents/updateStatus`

**Request:** `{ "documentId": "...", "status": "ready | failed | cancelled | rejected", "chunkCount": 87, "error": "...optional..." }`

**Response 200:** `{ "updated": true }`. `chunkCount`/`error` are omitted when not relevant to the transition.

---

## Convex → FastAPI

### `cleanupSession`

Called by the hourly Convex expiry cron (ADR-0006). Public, secret-gated, **idempotent**.

**Request (POST `/internal/cleanupSession`, `X-Service-Secret`):**
```json
{ "session_id": "...", "user_id": "...", "storage_paths": ["..."] }
```
FastAPI has no Convex read access outside purpose-built endpoints (ADR-0003/0010), so the cron resolves `userId` (for the RLS-scoped delete, ADR-0009) and every `documents.storagePath` for the session up front and hands both over — it cannot look them up itself mid-request.

**Behavior:** delete all of the session's chunks from Supabase pgvector (including the `is_scope_anchor` chunk, scoped via `user_scoped_tx`) and all raw PDFs at the given storage paths from Supabase Storage. Re-running on already-clean data is a no-op.

**Response 200:** `{ "session_id": "...", "deleted": true }`

On success Convex sets `session.status: "expired"`; on any non-200 the session stays `active` for the next hourly run to retry (ADR-0006).
