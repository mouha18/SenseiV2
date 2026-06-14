# TECHNICAL ROADMAP — Sensei

**Version:** 1.0
**Last Updated:** 2026-06-10

---

## 1. Project File Structure

```text
sensei/
│
├── frontend/                          # Next.js App Router frontend
│   ├── app/
│   │   ├── layout.tsx                 # Root layout, Convex provider
│   │   ├── page.tsx                   # Landing page
│   │   ├── (auth)/
│   │   │   ├── login/page.tsx
│   │   │   └── signup/page.tsx
│   │   ├── dashboard/
│   │   │   └── page.tsx               # Session list + new session CTA
│   │   ├── session/
│   │   │   └── [id]/page.tsx          # Active chat session
│   │   └── settings/
│   │       └── page.tsx               # Gemini API key input
│   ├── components/
│   │   ├── chat/
│   │   │   ├── ChatWindow.tsx         # Message list
│   │   │   ├── MessageBubble.tsx      # Single message, shows response type badge
│   │   │   ├── ChatInput.tsx          # Text input + send button
│   │   │   └── TestMeButton.tsx       # Triggers Feynman mode
│   │   ├── feynman/
│   │   │   ├── FeynmanModal.tsx       # Concept picker + explanation input
│   │   │   └── FeynmanResult.tsx      # Score breakdown + criticism display
│   │   ├── session/
│   │   │   ├── SessionCard.tsx        # Dashboard session list item
│   │   │   ├── UploadZone.tsx         # PDF drag-and-drop upload
│   │   │   └── ScopeTag.tsx           # Shows detected session topic
│   │   └── ui/                        # Shared primitives (Button, Input, Modal)
│   ├── convex/
│   │   ├── schema.ts                  # Convex table definitions
│   │   ├── users.ts                   # User queries/mutations (key, allowance, velocity, tokensValidAfter)
│   │   ├── sessions.ts                # Session mutations and queries
│   │   ├── documents.ts               # Document status mutations and queries (ADR-0005)
│   │   ├── messages.ts                # Message queries (client) + internal write mutations (server, ADR-0010)
│   │   ├── feynmanScores.ts           # Feynman score queries (client) + internal write mutation (server, ADR-0010)
│   │   ├── crons.ts                   # Hourly session-expiry cron (ADR-0006)
│   │   └── http.ts                    # FastAPI-facing service endpoints (INTERNAL_API.md; ADR-0003/0010)
│   ├── lib/
│   │   ├── api.ts                     # FastAPI client (typed fetch wrapper)
│   │   └── utils.ts                   # Shared helpers
│   └── .env.local
│
├── sensei-api/                        # FastAPI AI backend
│   ├── main.py                        # App entry, CORS, router registration
│   ├── config.py                      # Pydantic settings, reads from .env
│   ├── dependencies.py                # get_current_user (offline JWKS); velocity is enforced in Convex (ADR-0001), not in-process
│   ├── routers/
│   │   ├── ingest.py                  # /ingest routes (async upload, cancel)
│   │   ├── chat.py                    # /chat routes
│   │   ├── evaluate.py                # /evaluate routes
│   │   ├── keys.py                    # BYOK validate + encrypt (ADR-0002)
│   │   └── internal.py               # service-secret routes: expiry cleanup (ADR-0006)
│   ├── services/
│   │   ├── embedder.py                # PDF extraction, chunking, embedding, storage
│   │   ├── retriever.py               # Vector similarity search
│   │   ├── scorer.py                  # 7C's Feynman evaluation prompt builder
│   │   └── gemini.py                  # Single Gemini API caller
│   ├── models/
│   │   ├── ingest.py                  # Pydantic models for ingest routes
│   │   ├── chat.py                    # Pydantic models for chat routes
│   │   └── evaluate.py                # Pydantic models for evaluate routes
│   ├── utils/
│   │   └── scope.py                   # Scope extraction and checking helpers
│   ├── requirements.txt
│   └── .env
│
└── docs/                              # This documentation bundle
```

---

## 2. Type Definitions

```typescript
// Convex entity types

interface User {
  _id: Id<"users">;
  email: string;
  geminiApiKey?: string;        // ciphertext; absent → Default Key (ADR-0002)
  dailyDefaultKeyCount: number; // Daily Allowance counter (ADR-0001)
  dailyCountResetAt: number;    // next UTC midnight
  velocityCount: number;        // requests in current 60s window (ADR-0001)
  velocityWindowStart: number;  // when the current velocity window opened (ADR-0001)
  tokensValidAfter: number;     // logout/revoke clock (ADR-0003)
  onboardedAt?: number;         // set on tour finish/skip; absent → show tour
  createdAt: number;
}

interface Session {
  _id: Id<"sessions">;
  userId: Id<"users">;
  scope?: string;
  scopeDescription?: string; // embedded as the scope anchor for doc-less sessions (ADR-0004)
  scopeSource?: "document" | "first_question";
  status: "active" | "expired";
  outOfScopeCount: number;
  totalChunks: number;
  totalStorageBytes: number;
  lastActivityAt: number;
  createdAt: number;
}

interface Document {
  _id: Id<"documents">;
  sessionId: Id<"sessions">;
  userId: Id<"users">;
  fileName: string;
  fileSizeBytes: number;
  status: "processing" | "ready" | "failed" | "cancelled"; // ADR-0005
  chunkCount: number;
  storagePath: string; // raw PDF location in Supabase Storage (for expiry delete)
  error?: string;
  createdAt: number;
}

interface Message {
  _id: Id<"messages">;
  sessionId: Id<"sessions">;
  userId: Id<"users">;
  role: "user" | "assistant";
  content: string;
  responseType?: "socratic" | "direct" | "redirect" | "new_session_prompt";
  source?: "rag" | "general" | null;
  createdAt: number;
}

interface FeynmanScore {
  _id: Id<"feynmanScores">;
  sessionId: Id<"sessions">;
  userId: Id<"users">;
  concept: string;
  explanation: string;
  overallScore: number;
  scoresClear: number;
  scoresConcise: number;
  scoresConcrete: number;
  scoresCorrect: number;
  scoresCoherent: number;
  scoresComplete: number;
  scoresCourteous: number;
  criticism: string; // JSON string
  summary: string;
  attemptNumber: number;
  createdAt: number;
}

// API wrapper types

interface ApiResponse<T> {
  data: T;
  error: null;
}

interface ApiError {
  error: {
    code: string;
    message: string;
    detail: Record<string, unknown> | null;
  };
}

// FastAPI request/response types (mirrored in frontend lib/api.ts)

interface AskRequest {
  session_id: string;
  question: string;
  // gemini_api_key removed — FastAPI fetches + decrypts the key itself (ADR-0002)
  // out_of_scope_count removed — Convex-owned (ADR-0004)
  // conversation_history removed — FastAPI reads last N from Convex server-side (ADR-0010)
}

interface AskResponse {
  answer: string;
  response_type: "socratic" | "direct" | "redirect" | "new_session_prompt";
  source: "rag" | "general" | null;
  chunks_used: number;
  out_of_scope: boolean;
  new_session_required: boolean;
}

interface FeynmanRequest {
  session_id: string;
  concept: string;
  explanation: string;
  // gemini_api_key removed — FastAPI fetches + decrypts the key itself (ADR-0002)
}

interface FeynmanResponse {
  concept: string;
  overall_score: number;
  scores: {
    clear: number;
    concise: number;
    concrete: number;
    correct: number;
    coherent: number;
    complete: number;
    courteous: number;
  };
  criticism: Record<string, string>;
  summary: string;
  retry_suggested: boolean;
}
```

---

## 3. Function Signatures

### `convex/sessions.ts`

> The write mutations below (`updateSessionScope`, `incrementOutOfScopeCount`, `resetOutOfScopeCount`, `updateLastActivity`) are invoked by the **service layer** — `persistTurn` and ingestion — not by the client (ADR-0010/0011). Queries stay client-facing for subscriptions.

```typescript
// Queries
export const getSession = query({
  args: { sessionId: v.id("sessions") },
  handler: async (ctx, { sessionId }): Promise<Session | null>
});

export const getUserSessions = query({
  args: { userId: v.id("users") },
  handler: async (ctx, { userId }): Promise<Session[]>
});

// Mutations
export const createSession = mutation({
  args: { userId: v.id("users") },
  handler: async (ctx, { userId }): Promise<Id<"sessions">>
});

export const updateSessionScope = mutation({
  args: { sessionId: v.id("sessions"), scope: v.string(), scopeSource: v.string() },
  handler: async (ctx, args): Promise<void>
});

export const incrementOutOfScopeCount = mutation({
  args: { sessionId: v.id("sessions") },
  handler: async (ctx, { sessionId }): Promise<number>
});

export const resetOutOfScopeCount = mutation({
  args: { sessionId: v.id("sessions") },
  handler: async (ctx, { sessionId }): Promise<void>
});

export const updateLastActivity = mutation({
  args: { sessionId: v.id("sessions") },
  handler: async (ctx, { sessionId }): Promise<void>
});
```

### `convex/messages.ts`

> `addMessage` is **internal**, invoked by the `persistTurn` service endpoint (server-authoritative writes, ADR-0010) — not called by the client. `getSessionMessages` stays a client query for the real-time subscription.

```typescript
export const getSessionMessages = query({
  args: { sessionId: v.id("sessions") },
  handler: async (ctx, { sessionId }): Promise<Message[]>
});

export const addMessage = mutation({
  args: {
    sessionId: v.id("sessions"),
    userId: v.id("users"),
    role: v.string(),
    content: v.string(),
    responseType: v.optional(v.string()),
    source: v.optional(v.string()),
  },
  handler: async (ctx, args): Promise<Id<"messages">>
});
```

### `convex/feynmanScores.ts`

> `saveFeynmanScore` is **internal**, invoked by the `persistFeynman` service endpoint (server-authoritative writes, ADR-0010) — not called by the client. It computes `attemptNumber` server-side. `getSessionScores` stays a client query for the subscription.

```typescript
export const getSessionScores = query({
  args: { sessionId: v.id("sessions") },
  handler: async (ctx, { sessionId }): Promise<FeynmanScore[]>
});

export const saveFeynmanScore = mutation({
  args: { /* all FeynmanScore fields except _id */ },
  handler: async (ctx, args): Promise<Id<"feynmanScores">>
});
```

### `convex/documents.ts`
```typescript
export const getSessionDocuments = query({
  args: { sessionId: v.id("sessions") },
  handler: async (ctx, { sessionId }): Promise<Document[]> // real-time status (ADR-0005)
});

export const setDocumentStatus = mutation({
  args: { documentId: v.id("documents"), status: v.string(), chunkCount: v.optional(v.number()), error: v.optional(v.string()) },
  handler: async (ctx, args): Promise<void>
});
```

### `lib/api.ts`
```typescript
export async function askQuestion(
  payload: AskRequest,
  token: string
): Promise<AskResponse>

export async function uploadDocument(
  file: File,
  sessionId: string,
  token: string
): Promise<{ status: string; document_id: string; estimated_chunks: number }>

export async function cancelUpload(
  documentId: string,
  token: string
): Promise<{ document_id: string; status: "cancelled" }>

export async function evaluateFeynman(
  payload: FeynmanRequest,
  token: string
): Promise<FeynmanResponse>
```

---

## 4. Exact Data Flows

### Ask a Question
```text
ChatInput (component)
  → user types question, hits send
  → calls askQuestion() from lib/api.ts with { session_id, question } (no history, no key — ADR-0002/0010)
    → POST /chat/ask to FastAPI
    → FastAPI: verify JWT
    → getRequestContext (Convex service endpoint): velocity check-and-consume + key blob + session + last N messages (INTERNAL_API; ADR-0001/0010)
        → velocity exceeded → 429 RATE_LIMITED. session expired → 403 SESSION_EXPIRED
    → scope gate: embed question (gemini-embedding-001, 1536-dim) → band + borderline un-metered LLM scope-judge, both modes (doc 0.59–0.66, doc-less 0.57–0.63; no fixed threshold separates either — ADR-0004 amendment)
        → out of scope → persistTurn(redirect) (increments outOfScopeCount server-side) → return redirect / new_session_prompt
    → in scope: RAG retrieve (reuses the embedding) or general → Default Key? consumeAllowance (Convex) → Gemini (role-locked, server-read history)
    → persistTurn (Convex service endpoint): writes user + assistant message + bumps lastActivityAt + resets outOfScopeCount; on Gemini failure, refunds allowance and writes no assistant message (ADR-0010/0001)
    → returns AskResponse (for optimistic render)
  → ChatWindow re-renders from the Convex messages subscription — the client does NOT write messages (ADR-0010)
```

### Upload Document
```text
UploadZone (component)
  → user drops PDF
  → calls uploadDocument() from lib/api.ts
    → POST /ingest/upload to FastAPI
    → FastAPI: verify JWT → cheap guards (≤5MB file, ≤20MB session, not already at chunk cap) → create documents row (processing) → store raw PDF → start background pipeline
    → returns { status: "processing", document_id, estimated_chunks }
  → background pipeline: extract → chunk → compact (dedup + boilerplate) → scope-gate (gated uploads only) → cap-check → batch-embed → store (ADR-0005/0011)
      → first interaction in the session → derives & locks scope (FastAPI writes sessions.scope server-side); later uploads → gated, not deriving (ADR-0011)
      → terminal status: ready | failed (incl. non-extractable/scanned PDF) | cancelled | rejected (off-topic upload — chunks+PDF deleted)
  → subscribe to the Convex documents row for live status (no polling — ADR-0005)
  → ScopeTag updates from session.scope; a "rejected"/"failed" status shows its message
```

### Feynman Evaluation
```text
TestMeButton (component)
  → opens FeynmanModal
  → user selects concept + types explanation + submits
  → calls evaluateFeynman() from lib/api.ts
    → POST /evaluate/feynman to FastAPI
    → FastAPI: verify JWT → getRequestContext (velocity + key + session) → retriever.py gets concept chunks → Default Key? consumeAllowance → scorer.py builds calibrated rubric (ADR-0007) → Gemini scores → overall = six-C average computed in code (Courteous excluded)
    → persistFeynman (Convex service endpoint): writes the score (attemptNumber computed server-side) + bumps lastActivityAt; on failure refunds allowance, writes nothing (ADR-0010/0001)
    → returns FeynmanResponse (retry_suggested = overall < 70)
  → FeynmanResult renders from the Convex scores subscription — the client does NOT write the score (ADR-0010)
  → "Try Again" resets modal with same concept pre-filled; "Continue" closes modal
```

---

## 5. Files to Create vs. Modify

### Create from scratch

| File | Purpose |
|---|---|
| `sensei-api/main.py` | FastAPI app entry, CORS, router registration |
| `sensei-api/config.py` | Pydantic settings — reads all env vars |
| `sensei-api/dependencies.py` | Auth verification (offline JWKS); velocity is enforced in Convex (ADR-0001) |
| `sensei-api/routers/ingest.py` | Async upload + cancel routes |
| `sensei-api/routers/chat.py` | Ask route |
| `sensei-api/routers/evaluate.py` | Feynman route |
| `sensei-api/services/embedder.py` | PDF processing + vector storage |
| `sensei-api/services/retriever.py` | Vector similarity search |
| `sensei-api/services/scorer.py` | 7C's evaluation prompt |
| `sensei-api/services/gemini.py` | Gemini API wrapper |
| `sensei-api/utils/scope.py` | Scope extraction and checking |
| `sensei-api/models/*.py` | All Pydantic request/response models |
| `frontend/convex/schema.ts` | Convex table definitions |
| `frontend/convex/sessions.ts` | Session queries and mutations |
| `frontend/convex/messages.ts` | Message queries and mutations |
| `frontend/convex/feynmanScores.ts` | Feynman score queries and mutations |
| `frontend/convex/documents.ts` | Document status queries and mutations (ADR-0005) |
| `frontend/convex/crons.ts` | Hourly session-expiry cron (ADR-0006) |
| `sensei-api/routers/keys.py` | BYOK validate + encrypt (ADR-0002) |
| `sensei-api/routers/internal.py` | Service-secret expiry cleanup (ADR-0006) |
| `frontend/lib/api.ts` | FastAPI typed fetch client |
| `frontend/components/chat/*` | All chat UI components |
| `frontend/components/feynman/*` | Feynman modal and result components |
| `frontend/components/session/*` | Session card, upload zone, scope tag |

### Modify existing

| File | What to change |
|---|---|
| `frontend/app/layout.tsx` | Add Convex provider wrapper |
| `frontend/app/session/[id]/page.tsx` | Wire ChatWindow, UploadZone, TestMeButton |

---

## 6. Component Interaction Map

```text
app/session/[id]/page.tsx
  ├── useSession(sessionId)           → Convex query, real-time
  ├── useMessages(sessionId)          → Convex query, real-time
  ├── UploadZone
  │     └── uploadDocument()          → lib/api.ts → FastAPI
  ├── ScopeTag
  │     └── reads session.scope       → from useSession
  ├── ChatWindow
  │     └── MessageBubble[]           → renders messages from useMessages
  ├── ChatInput
  │     └── askQuestion()             → lib/api.ts → FastAPI
  │           → FastAPI persistTurn (server-authoritative write, ADR-0010)
  │           → ChatWindow re-renders from useMessages subscription
  └── TestMeButton
        └── opens FeynmanModal
              └── evaluateFeynman()   → lib/api.ts → FastAPI
                    → FastAPI persistFeynman (server-authoritative write, ADR-0010)
                    → FeynmanResult renders from useSessionScores subscription
```

**State ownership:**

| State | Lives in | Shared via |
|---|---|---|
| Session metadata (scope, status) | Convex | `useSession` hook |
| Chat messages | Convex | `useMessages` hook |
| Feynman scores | Convex | `useSessionScores` hook |
| Out-of-scope count | Convex (`sessions.outOfScopeCount`) | `useSession` hook |
| Feynman modal open/closed | Local component state | Props |
| Upload progress | Local component state | Props |

---

**Context window management:** FastAPI reads only the last 20 messages from Convex **server-side** (via `getRequestContext`, ADR-0010) — the client no longer fetches or passes history. This keeps the Gemini prompt within token limits for long sessions. The number 20 is a safe starting point — adjust based on average message length if needed.

## 7. Build Order

1. Convex schema (`schema.ts`) — everything depends on this
2. Pydantic models in FastAPI (`models/`) — define the contract before implementing
3. FastAPI skeleton — `main.py`, `config.py`, `dependencies.py`, empty routers
4. Auth flow — Convex Auth + JWKS verification (`get_current_user`) + service secret for FastAPI→Convex (ADR-0003)
5. `gemini.py` service — needed by everything else in FastAPI
6. `embedder.py` + Supabase pgvector setup — RAG foundation
7. `retriever.py` — depends on embedder having stored chunks
8. Ingest router — async upload + cancel; Convex documents table + subscription (ADR-0005)
9. `utils/scope.py` — needed before chat route
10. Chat router + Socratic logic + Daily Allowance enforcement (ADR-0001) — core feature
11. `scorer.py` service — Feynman evaluation prompt
12. Evaluate router — wires scorer + retriever
13. Convex mutations and queries — sessions, messages, feynmanScores, documents, users (allowance), crons (expiry)
14. Frontend: Convex provider + auth pages
15. Frontend: dashboard + session creation
16. Frontend: ChatWindow + ChatInput + UploadZone
17. Frontend: TestMeButton + FeynmanModal + FeynmanResult
18. Frontend: settings page (Gemini key input)
19. Error states, loading states, empty states
20. Rate limiting, scope enforcement, role-lock — end-to-end test
