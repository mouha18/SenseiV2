# DATABASE SCHEMA — Sensei

**Databases:** Convex (relational-style, real-time) + Supabase Postgres (pgvector)
**Naming convention:** camelCase for Convex, snake_case for Supabase

---

## Convex Tables

### `users`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `_id` | Id | PK, auto | Convex document ID |
| `email` | string | unique, required | User email |
| `geminiApiKey` | string | optional, encrypted | User's Gemini API key (BYOK). When absent, the Default Key is used |
| `dailyDefaultKeyCount` | number | required, default 0 | Messages sent today on the Default Key — the Daily Allowance counter (see ADR-0001) |
| `dailyCountResetAt` | number | required | Unix timestamp of next UTC midnight; counter resets to 0 when `now ≥ dailyCountResetAt` |
| `velocityCount` | number | required, default 0 | Requests in the current 60s window — velocity rate limit (ADR-0001) |
| `velocityWindowStart` | number | required, default 0 | Unix ms the current velocity window opened; a new window opens when `now − velocityWindowStart ≥ 60s`. Not restamped on in-window requests |
| `tokensValidAfter` | number | required, default 0 | Unix timestamp; a token whose issued-at (`iat`) is before this is rejected. Logout/revoke-all sets it to now |
| `onboardedAt` | number | optional | Unix timestamp set when the user finishes or skips the onboarding tour; absent → tour shown (first-time-only) |
| `createdAt` | number | required | Unix timestamp |

---

### `sessions`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `_id` | Id | PK, auto | Convex document ID |
| `userId` | Id | required, FK → users | Owner of the session |
| `scope` | string | optional | Auto-detected topic label (e.g. "French History") — shown to the student |
| `scopeDescription` | string | optional | Gemini-drawn topic description; its embedding is the scope anchor for doc-less sessions (ADR-0004) |
| `scopeSource` | string | optional | "document" or "first_question" |
| `status` | string | required | "active" or "expired" |
| `outOfScopeCount` | number | required, default 0 | Consecutive out-of-scope message count |
| `totalChunks` | number | required, default 0 | Number of chunks stored in Supabase for this session |
| `totalStorageBytes` | number | required, default 0 | Total bytes of uploaded files — capped at 20MB per session |
| `lastActivityAt` | number | required | Unix timestamp of the last chat/Feynman/upload action; sole clock for 3-day expiry (ADR-0006) |
| `createdAt` | number | required | Unix timestamp |

---

### `messages`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `_id` | Id | PK, auto | Convex document ID |
| `sessionId` | Id | required, FK → sessions | Parent session |
| `userId` | Id | required, FK → users | Message author |
| `role` | string | required | "user" or "assistant" |
| `content` | string | required | Message text |
| `responseType` | string | optional | "socratic", "direct", "redirect", "new_session_prompt" |
| `source` | string | optional | "rag", "general", or null |
| `createdAt` | number | required | Unix timestamp |

---

### `feynmanScores`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `_id` | Id | PK, auto | Convex document ID |
| `sessionId` | Id | required, FK → sessions | Parent session |
| `userId` | Id | required, FK → users | Student |
| `concept` | string | required | Concept that was explained |
| `explanation` | string | required | Student's raw explanation text |
| `overallScore` | number | required | 0–100 |
| `scoresClear` | number | required | 0–100 |
| `scoresConcise` | number | required | 0–100 |
| `scoresConcrete` | number | required | 0–100 |
| `scoresCorrect` | number | required | 0–100 |
| `scoresCoherent` | number | required | 0–100 |
| `scoresComplete` | number | required | 0–100 |
| `scoresCourteous` | number | required | 0–100 |
| `criticism` | string | required | JSON string of per-criterion criticism |
| `summary` | string | required | Overall feedback summary |
| `attemptNumber` | number | required | Which attempt this is (1, 2, 3...) |
| `createdAt` | number | required | Unix timestamp |

---

### `documents`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `_id` | Id | PK, auto | Convex document ID — this is the `document_id` returned by the API |
| `sessionId` | Id | required, FK → sessions | Parent session |
| `userId` | Id | required, FK → users | Owner |
| `fileName` | string | required | Original file name |
| `fileSizeBytes` | number | required | File size — feeds the 20MB/session cap |
| `status` | string | required | "processing", "ready", "failed", "cancelled" (ADR-0005), or "rejected" — off-topic upload to a scope-locked session; chunks + PDF deleted (ADR-0011) |
| `chunkCount` | number | required, default 0 | Chunks produced — feeds the 200-chunk/session cap |
| `storagePath` | string | required | Path of the raw PDF in Supabase Storage — used to delete it on session expiry |
| `error` | string | optional | Failure reason when status is "failed" |
| `createdAt` | number | required | Unix timestamp |

---

## Supabase Tables

### `chunks`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | uuid | PK, default gen_random_uuid() | Chunk ID |
| `user_id` | text | required, indexed | Convex user ID (string) |
| `session_id` | text | required, indexed | Convex session ID (string) |
| `document_id` | text | required | Convex document reference |
| `content` | text | required | Raw chunk text |
| `embedding` | vector(1536) | required | Embedding vector — `gemini-embedding-001`, MRL-truncated to 1536 dims (under pgvector's 2000-dim index cap; `text-embedding-004` was retired Jan 2026) |
| `page_number` | integer | optional | Source page in the PDF |
| `book_title` | text | optional | Source document title |
| `chunk_index` | integer | required | Position of chunk in document |
| `is_scope_anchor` | boolean | default false | True for the synthetic scope-anchor chunk in doc-less sessions; excluded from RAG retrieval (ADR-0004) |
| `created_at` | timestamptz | default now() | Creation timestamp |

---

## Indexes

```sql
-- Supabase: fast vector similarity search scoped to session
CREATE INDEX ON chunks USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);

-- Supabase: fast lookup by session
CREATE INDEX idx_chunks_session ON chunks (session_id);

-- Supabase: fast lookup by user
CREATE INDEX idx_chunks_user ON chunks (user_id);
```

---

## Relationships

- `sessions.userId` → `users._id` (many sessions per user)
- `messages.sessionId` → `sessions._id` (many messages per session)
- `messages.userId` → `users._id` (user authorship)
- `feynmanScores.sessionId` → `sessions._id` (many Feynman attempts per session)
- `feynmanScores.userId` → `users._id` (user authorship)
- `documents.sessionId` → `sessions._id` (many documents per session)
- `documents.userId` → `users._id` (user authorship)
- `chunks.session_id` → Convex `sessions._id` (string foreign key, not enforced at DB level — enforced in application)
- `chunks.document_id` → Convex `documents._id` (string foreign key, enforced in application)

---

## Access Control

```sql
-- Supabase RLS: users can only access their own chunks
ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can read own chunks"
  ON chunks FOR SELECT
  USING (user_id = current_setting('app.current_user_id'));

CREATE POLICY "Users can insert own chunks"
  ON chunks FOR INSERT
  WITH CHECK (user_id = current_setting('app.current_user_id'));

CREATE POLICY "Users can delete own chunks"
  ON chunks FOR DELETE
  USING (user_id = current_setting('app.current_user_id'));
```

FastAPI sets `app.current_user_id` on each Supabase connection after verifying the Convex token.

---

## Migrations

```text
supabase/migrations/
├── 20260610_001_create_chunks_table.sql
├── 20260610_002_create_chunks_indexes.sql
└── 20260610_003_enable_rls_chunks.sql
```
