# API CONTRACT — Sensei

Full request and response shapes for every endpoint.

---

## GET /health

**Request:** No body, no auth.

**Response 200:**
```json
{
  "status": "ok",
  "version": "1.0.0"
}
```

---

## POST /ingest/upload

**Description:** Upload a PDF file for a session. FastAPI extracts, chunks, embeds, and stores in Supabase.

**Headers:**
```text
Authorization: Bearer <convex_session_token>
Content-Type: multipart/form-data
```

**Request (multipart form):**
```text
file: <PDF binary>
session_id: "sess_abc123"
```

**Response 200:**
```json
{
  "status": "processing",
  "document_id": "doc_xyz789",
  "session_id": "sess_abc123",
  "file_name": "french_history.pdf",
  "file_size_bytes": 4200000,
  "estimated_chunks": 87
}
```

**Response 400 — file too large:**
```json
{
  "error": {
    "code": "STORAGE_LIMIT",
    "message": "File exceeds the 5MB per-file limit.",
    "detail": { "file_size_bytes": 8000000, "limit_bytes": 5242880 }
  }
}
```

**Response 400 — session storage full:**
```json
{
  "error": {
    "code": "STORAGE_LIMIT",
    "message": "Session storage limit of 20MB reached.",
    "detail": { "current_bytes": 20000000, "limit_bytes": 20971520 }
  }
}
```

---

## Ingestion status

Document status (`processing` / `ready` / `failed` / `cancelled` / `rejected`) lives in the Convex `documents` table and is consumed by the frontend via a real-time Convex subscription — there is no FastAPI status endpoint (see ADR-0005). `rejected` means an off-topic upload to a scope-locked session — chunks + PDF deleted, with an upload-redirect message (ADR-0011).

---

## POST /ingest/cancel

**Description:** Stop an in-progress document upload. Cancellation is cooperative — processing halts at the next checkpoint, then the document's partial chunks and raw PDF are hard-deleted.

**Headers:**
```text
Authorization: Bearer <convex_session_token>
Content-Type: application/json
```

**Request:**
```json
{
  "document_id": "doc_xyz789"
}
```

**Response 200:**
```json
{
  "document_id": "doc_xyz789",
  "status": "cancelled"
}
```

**Response 404 — unknown or not owned:**
```json
{
  "error": {
    "code": "DOCUMENT_NOT_FOUND",
    "message": "No in-progress document with that ID in this session."
  }
}
```

---

## POST /chat/ask

**Description:** Send a student question. Returns a Socratic or direct answer based on question type and session context.

**Headers:**
```text
Authorization: Bearer <convex_session_token>
Content-Type: application/json
```

**Request:**
```json
{
  "session_id": "sess_abc123",
  "question": "What caused the French Revolution?"
}
```

> Conversation history is **not** sent by the client. FastAPI reads the last N messages from Convex server-side and is the authoritative writer of the turn (user + assistant message) — see ADR-0010. The answer is also returned in the response below for optimistic rendering; the canonical record arrives via the Convex subscription.

**Response 200 — normal answer:**
```json
{
  "answer": "Before I explain, let me ask you this: what do you think happens to a population when food prices double while wages stay the same?",
  "response_type": "socratic",
  "source": "rag",
  "chunks_used": 3,
  "out_of_scope": false,
  "new_session_required": false
}
```

**Response 200 — out of scope:**
```json
{
  "answer": "We're focusing on French History today. Let's stay on track — do you have a question about the Revolution or the Ancien Régime?",
  "response_type": "redirect",
  "source": null,
  "chunks_used": 0,
  "out_of_scope": true,
  "new_session_required": false
}
```

**Response 200 — new session required (3 strikes):**
```json
{
  "answer": "It looks like you want to explore a different topic. Would you like to start a new session on that subject?",
  "response_type": "new_session_prompt",
  "source": null,
  "chunks_used": 0,
  "out_of_scope": true,
  "new_session_required": true
}
```

**Response 409 — document still processing:**
```json
{
  "error": {
    "code": "INGEST_IN_PROGRESS",
    "message": "A document is still being processed for this session. Please wait until it's ready."
  }
}
```

**Response types:**
| Value | Meaning |
|---|---|
| `socratic` | Guiding question returned |
| `direct` | Direct answer (factual or post-Socratic exchange) |
| `redirect` | Out of scope message |
| `new_session_prompt` | 3 strikes — prompt to create new session |

**Source types:**
| Value | Meaning |
|---|---|
| `rag` | Answer grounded in uploaded documents |
| `general` | Answer from Gemini general knowledge |
| `null` | No AI call made (redirect or rejection) |

---

## POST /evaluate/feynman

**Description:** Evaluate a student's free-form explanation of a concept using the 7C's rubric.

**Headers:**
```text
Authorization: Bearer <convex_session_token>
Content-Type: application/json
```

**Request:**
```json
{
  "session_id": "sess_abc123",
  "concept": "Compound Interest",
  "explanation": "Compound interest is when you earn interest not just on your original money but also on the interest you already earned. So if you have 100 dollars and earn 10 percent, next year you earn interest on 110 dollars instead of 100."
}
```

**Response 200:**
```json
{
  "concept": "Compound Interest",
  "overall_score": 76,
  "scores": {
    "clear": 80,
    "concise": 85,
    "concrete": 90,
    "correct": 75,
    "coherent": 70,
    "complete": 55,
    "courteous": 80
  },
  "criticism": {
    "clear": "Your explanation is easy to follow and avoids jargon. Well done.",
    "concise": "Good length — you got to the point without padding.",
    "concrete": "The 100 dollar example is effective and well-placed.",
    "correct": "The core idea is accurate. However, you didn't mention that the compounding frequency (daily vs yearly) affects the outcome significantly.",
    "coherent": "The flow is logical but the transition from definition to example could be smoother.",
    "complete": "You missed the concept of the compounding period and how it multiplies the effect over long time horizons. This is a key part of why compound interest is powerful.",
    "courteous": "Confident and clear tone throughout."
  },
  "summary": "Strong start with a good concrete example. The main gap is completeness — compounding frequency and long-term exponential growth are central to this concept and weren't covered.",
  "retry_suggested": false
}
```

> `overall_score` is the equal-weighted average of the **six understanding criteria** (Clear, Concise, Concrete, Correct, Coherent, Complete), computed in code. `courteous` is scored and returned for feedback but **excluded** from the overall — see ADR-0007. Here: `(80+85+90+75+70+55)/6 ≈ 76`. `retry_suggested` is `true` when `overall_score < 70` (ADR-0007); 76 ≥ 70, so it's `false` here.

---

## Common errors

### `SESSION_EXPIRED`

Returned by the three write routes — `POST /chat/ask`, `POST /ingest/upload`, `POST /evaluate/feynman` — when the target session has expired. Expired sessions are read-only: chat history and Feynman scores remain readable, but no new writes are accepted (ADR-0006).

**Response 403:**
```json
{
  "error": {
    "code": "SESSION_EXPIRED",
    "message": "This session has expired and is read-only. Start a new session to continue."
  }
}
```

### `ALLOWANCE_EXHAUSTED`

Returned by `POST /chat/ask` and `POST /evaluate/feynman` when a student on the Default Key has used their Daily Allowance (default 20 generation calls/day). The cap resets at UTC midnight; adding a personal Gemini key (BYOK) lifts it immediately (ADR-0001, ADR-0007). Distinct from the per-minute velocity rate limit, which also returns 429 but with a different code.

**Response 429:**
```json
{
  "error": {
    "code": "ALLOWANCE_EXHAUSTED",
    "message": "You've used your free daily allowance. Add your own Gemini key to keep going, or wait until tomorrow.",
    "detail": { "resets_at": 1749700800000 }
  }
}
```

### `GENERATION_FAILED`

Returned by `POST /chat/ask` and `POST /evaluate/feynman` when Gemini returns no usable answer — a transport error, a 5xx, a timeout, a safety-filter block, or schema-invalid output that survives one retry (PROMPTS.md conventions). The Daily Allowance is refunded if it had been consumed for this request (ADR-0001); nothing is persisted to chat history beyond what `persistTurn`'s `"failed"` outcome already covers (ADR-0010).

**Response 502:**
```json
{
  "error": {
    "code": "GENERATION_FAILED",
    "message": "Something went wrong generating a response. Please try asking again."
  }
}
```
