# IMPLEMENTATION ROADMAP — Sensei

**Version:** 1.0
**Last Updated:** 2026-06-10
**Total Sprints:** 8
**Sprint Length:** 1 week

---

## Status Legend

| Symbol | Meaning |
|---|---|
| ✅ | Done |
| 🔄 | In Progress |
| 📋 | Planned |
| ⏸ | Blocked |

---

#### Sprint 1 — Foundation
**Goal:** Project scaffolded, schema defined, environment set up, nothing is blocked by missing config.
**Deliverable:** Both repos run locally. Convex schema deployed. Supabase pgvector table created. FastAPI returns 200 on `/health`.

| # | Task | Type | Files Involved | Status |
|---|---|---|---|---|
| 1 | Scaffold Next.js frontend with App Router | `infra` | `frontend/` | 📋 |
| 2 | Scaffold FastAPI backend with virtual env | `infra` | `sensei-api/` | 📋 |
| 3 | Set up Convex project, deploy schema | `infra` | `convex/schema.ts` | 📋 |
| 4 | Set up Supabase: chunks table + pgvector + RLS, plus a **restricted (non-superuser) role** FastAPI connects as, and the `app.current_user_id` GUC for `SET LOCAL` (ADR-0009 — not the service key) | `infra` | Supabase dashboard + migrations | 📋 |
| 5 | Write all Pydantic models | `chore` | `sensei-api/models/*.py` | 📋 |
| 6 | Write `config.py` and `.env.example` for FastAPI | `chore` | `sensei-api/config.py` | 📋 |
| 7 | Register CORS, health route, empty routers in `main.py` | `chore` | `sensei-api/main.py` | 📋 |
| 8 | Write TypeScript types in `lib/api.ts` | `chore` | `frontend/lib/api.ts` | 📋 |

**Definition of Done:**
- [ ] `uvicorn main:app --reload` starts with no errors
- [ ] `GET /health` returns `{ status: "ok" }`
- [ ] `npm run dev` starts frontend with no errors
- [ ] Convex schema deployed — tables visible in Convex dashboard
- [ ] Supabase chunks table exists with pgvector index

---

#### Sprint 2 — Auth
**Goal:** Students can sign up, log in, and their identity flows through to FastAPI.
**Deliverable:** Full auth flow works end-to-end. FastAPI rejects requests without a valid token.

| # | Task | Type | Files Involved | Status |
|---|---|---|---|---|
| 1 | Set up Convex Auth (email/password) | `feat` | `convex/auth.ts`, `frontend/app/(auth)/` | 📋 |
| 2 | Build login and signup pages | `feat` | `frontend/app/(auth)/login/page.tsx`, `signup/page.tsx` | 📋 |
| 3 | Write `get_current_user` — offline JWKS verification + `tokensValidAfter` check (ADR-0003) | `feat` | `sensei-api/dependencies.py` | 📋 |
| 4 | Add auth guard to all non-health FastAPI routes | `feat` | `sensei-api/routers/*.py` | 📋 |
| 5 | BYOK key: FastAPI validate+encrypt endpoint, Convex stores ciphertext (ADR-0002); settings page | `feat` | `sensei-api/routers/keys.py`, `convex/users.ts`, `frontend/app/settings/page.tsx` | 📋 |

**Definition of Done:**
- [ ] Student can sign up and log in
- [ ] Convex session token issued on login
- [ ] FastAPI returns 401 on missing token
- [ ] FastAPI returns 200 when valid token provided
- [ ] Student can save Gemini API key in settings

---

#### Sprint 3 — RAG Pipeline (Backend)
**Goal:** PDF upload → chunked → embedded → stored in Supabase. Retrieval returns relevant chunks.
**Deliverable:** Upload a PDF via Postman, see chunks appear in Supabase.

| # | Task | Type | Files Involved | Status |
|---|---|---|---|---|
| 1 | Build `gemini.py` — Gemini API wrapper using student key | `feat` | `sensei-api/services/gemini.py` | 📋 |
| 2 | Build `embedder.py` — PDF extraction, chunking, embedding (gemini-embedding-001, 1536-dim, MRL-normalized, `RETRIEVAL_DOCUMENT`), Supabase insert | `feat` | `sensei-api/services/embedder.py` | 📋 |
| 3 | Build `retriever.py` — cosine similarity search scoped to session | `feat` | `sensei-api/services/retriever.py` | 📋 |
| 4 | Build ingest router — async upload + cancel routes; create/maintain Convex `documents` rows (ADR-0005) | `feat` | `sensei-api/routers/ingest.py` | 📋 |
| 5 | Ingestion pipeline guards: cheap upfront checks (≤5MB file, ≤20MB session, not already at cap) + background **compact → re-check → fail if still over 200**, and fail-fast on non-extractable/scanned PDFs (ADR-0005) | `feat` | `sensei-api/routers/ingest.py`, `embedder.py` | 📋 |
| 6 | Scope derivation from documents — locks the anchor on an upload-first session (ADR-0011) | `feat` | `sensei-api/utils/scope.py` | 📋 |
| 7 | Document scope-gate — sample-embed mid-session uploads vs the locked anchor; reject + delete off-topic, status `rejected` (ADR-0011) | `feat` | `sensei-api/services/embedder.py`, `utils/scope.py` | 📋 |

**Definition of Done:**
- [ ] POST /ingest/upload accepts a PDF and returns `{ status: "processing" }`
- [ ] Chunks appear in Supabase after upload
- [ ] Document status (`processing`/`ready`/`failed`/`cancelled`/`rejected`) visible via the Convex `documents` subscription — no status endpoint (ADR-0005)
- [ ] Upload rejected upfront if file > 5MB or the session is already ≥ 20MB / at the 200-chunk cap
- [ ] A document still over 200 chunks after compaction **fails** mid-pipeline (never truncated — ADR-0005)
- [ ] A scanned / non-extractable PDF fails with a clear message (no OCR — ADR-0005)
- [ ] An off-topic upload to a scope-locked session is `rejected`; its chunks + raw PDF are deleted (ADR-0011)
- [ ] In-progress upload can be cancelled; partial chunks + raw PDF hard-deleted (ADR-0005)

---

#### Sprint 4 — Chat Route + Socratic Logic (Backend)
**Goal:** Full chat pipeline working — scope check, RAG, Gemini call, three response modes.
**Deliverable:** POST /chat/ask returns correct response type for conceptual, factual, and out-of-scope questions.

| # | Task | Type | Files Involved | Status |
|---|---|---|---|---|
| 1 | Port the chat system prompt + assembly/delimiting and the borderline scope-judge prompt from `PROMPTS.md` (structured JSON via `response_schema`; gemini-3.1-flash-lite, thinking MINIMAL) (ADR-0008, ADR-0004) | `feat` | `sensei-api/services/gemini.py` | 📋 |
| 2 | Build scope check utility — **both** modes use a band + un-metered **LLM scope-judge** (no fixed threshold separates either; ADR-0004 amendment): doc **0.59–0.66** (judge grounded in label + top chunks), doc-less **0.57–0.63** (label + description); clear cases decide in code | `feat` | `sensei-api/utils/scope.py`, `services/gemini.py` | 📋 |
| 3 | Velocity limit (20/min) — fixed window on the Convex `users` row, consumed in the `getRequestContext` service call (ADR-0001 — not slowapi/in-memory) | `feat` | `convex/http.ts`, `convex/users.ts` | 📋 |
| 3b | Daily Allowance check/increment (Convex transactional mutation, **after** the in-scope decision) + Default Key/BYOK selection (ADR-0001/0004) | `feat` | `convex/users.ts`, `sensei-api/routers/chat.py` | 📋 |
| 3c | Service endpoints `getRequestContext` + `persistTurn` — server-authoritative reads/writes; velocity → scope → allowance → Gemini → persist (refund on failure) (ADR-0010; INTERNAL_API) | `feat` | `convex/http.ts`, `sensei-api/routers/chat.py` | 📋 |
| 4 | Build chat router — ask route with full pipeline | `feat` | `sensei-api/routers/chat.py` | 📋 |
| 5 | Implement three response modes in `gemini.py` (socratic, direct, application) | `feat` | `sensei-api/services/gemini.py` | 📋 |
| 6 | Implement out-of-scope redirect and 3-strike new-session prompt | `feat` | `sensei-api/routers/chat.py` | 📋 |
| 7 | Scope extraction from first question (no-document path) | `feat` | `sensei-api/utils/scope.py` | 📋 |

**Definition of Done:**
- [ ] Conceptual question returns `response_type: "socratic"`
- [ ] Factual question returns `response_type: "direct"`
- [ ] Out-of-scope question returns `response_type: "redirect"`
- [ ] 3rd out-of-scope returns `new_session_required: true`
- [ ] Role-change attempt ("act as…", persona/instruction override) stays in character (role-lock — ADR-0008)
- [ ] 21st request in a minute returns 429
- [ ] RAG path used when chunks exist; general knowledge used when they don't
- [ ] Messages are written **server-side by FastAPI** (`persistTurn`) — the client sends no history and writes no messages (ADR-0010)
- [ ] Velocity is checked before scope; the Daily Allowance is consumed only after the message is in-scope (out-of-scope costs no allowance — ADR-0004)
- [ ] Borderline questions route to the un-metered LLM scope-judge in **both** modes — doc 0.59–0.66, doc-less 0.57–0.63; clear cases decide in code (ADR-0004 amendment)
- [ ] Both scope bands re-calibrated against real traffic before launch (`/calibration` values are provisional — 8 synthetic topics, not real questions)

---

#### Sprint 5 — Feynman Evaluation (Backend)
**Goal:** Full Feynman evaluation pipeline working.
**Deliverable:** POST /evaluate/feynman returns 7C's scores + criticism for any explanation.

| # | Task | Type | Files Involved | Status |
|---|---|---|---|---|
| 1 | Build `scorer.py` — 7C's rubric prompt builder; overall = **six-C average, Courteous excluded**, computed in code (ADR-0007) | `feat` | `sensei-api/services/scorer.py` | 📋 |
| 2 | Build evaluate router — feynman route | `feat` | `sensei-api/routers/evaluate.py` | 📋 |
| 3 | `persistFeynman` service endpoint — server-authoritative score write (attemptNumber server-side) + refund-on-failure (ADR-0010) | `feat` | `convex/http.ts`, `sensei-api/routers/evaluate.py` | 📋 |
| 4 | Test scoring consistency across multiple explanations | `chore` | manual testing | 📋 |

**Definition of Done:**
- [ ] POST /evaluate/feynman returns scores for all 7 criteria
- [ ] Scores are 0–100 per criterion
- [ ] `overall_score` = average of the **six** understanding criteria, Courteous excluded (ADR-0007)
- [ ] Per-criterion criticism is specific and actionable
- [ ] `retry_suggested` is true when overall score < 70
- [ ] Relevant session chunks are used to check correctness
- [ ] The score is written **server-side by FastAPI** (`persistFeynman`), not the client (ADR-0010)

---

#### Sprint 6 — Frontend (Core UI)
**Goal:** Full frontend connected to backend. Student can have a real study session.
**Deliverable:** End-to-end session — login, upload, chat, Feynman — all working in the browser.

| # | Task | Type | Files Involved | Status |
|---|---|---|---|---|
| 1 | Build dashboard — session list + new session CTA | `feat` | `frontend/app/dashboard/page.tsx`, `SessionCard.tsx` | 📋 |
| 2 | Build session page — UploadZone + ScopeTag + ChatWindow + ChatInput | `feat` | `frontend/app/session/[id]/page.tsx`, `chat/*` | 📋 |
| 3 | Wire client Convex queries/subscriptions — create session; render messages + scope live. Messages/scores are **written server-side** by FastAPI, not the client (ADR-0010) | `feat` | `convex/sessions.ts`, `convex/messages.ts` | 📋 |
| 4 | Build Feynman flow — TestMeButton + FeynmanModal + FeynmanResult | `feat` | `frontend/components/feynman/*` | 📋 |
| 5 | Render Feynman result from the Convex scores subscription (the score is written server-side by FastAPI — ADR-0010) | `feat` | `convex/feynmanScores.ts` | 📋 |
| 6 | Build onboarding tour for first-time users | `feat` | `frontend/components/ui/OnboardingTour.tsx` | 📋 |

**Definition of Done:**
- [ ] Student can create a session, upload a PDF, and chat
- [ ] Scope tag appears after upload or first message
- [ ] Messages persist in Convex and re-render on page refresh
- [ ] Feynman modal opens, accepts explanation, shows score breakdown
- [ ] Feynman score saved to Convex
- [ ] Onboarding tour shows on first login only

---

#### Sprint 7 — Polish + Error States
**Goal:** Every failure case handled gracefully. No blank screens.
**Deliverable:** QA pass with no unhandled error states.

| # | Task | Type | Files Involved | Status |
|---|---|---|---|---|
| 1 | Handle Gemini API error (bad key, quota) in UI | `feat` | `frontend/components/chat/ChatInput.tsx` | ✅ |
| 2 | Handle ingestion outcomes in UI — failed (incl. scanned PDF), cancelled, and `rejected`/off-topic upload (ADR-0005/0011) | `feat` | `frontend/components/session/UploadZone.tsx` | ✅ |
| 3 | Handle **both** 429s in UI — `RATE_LIMITED` (velocity) and `ALLOWANCE_EXHAUSTED` (prompt to add a key) | `feat` | `frontend/lib/api.ts` | ✅ |
| 4 | Handle session expiry (expired sessions shown as read-only) | `feat` | `frontend/app/session/[id]/page.tsx` | ✅ |
| 5 | Loading states for all async operations | `feat` | all components with API calls | ✅ |
| 6 | Empty state for dashboard (no sessions yet) | `feat` | `frontend/app/dashboard/page.tsx` | ✅ |
| 7 | Session expiry cleanup — Convex hourly cron finds inactive sessions; FastAPI internal route hard-deletes chunks + raw PDFs and marks expired (ADR-0006) | `infra` | `convex/crons.ts`, `sensei-api/routers/internal.py` | ✅ |

**Definition of Done:**
- [x] Every API error shows a user-friendly message
- [x] No blank screens or unhandled promise rejections
- [x] Session expiry cleanup runs automatically (needs `FASTAPI_URL` set in Convex env + deploy to take effect live)

---

#### Sprint 8 — Testing + Deployment
**Goal:** MVP deployed to a live URL, shareable and stable.
**Deliverable:** Live URL with full Sensei functionality.

| # | Task | Type | Files Involved | Status |
|---|---|---|---|---|
| 1 | End-to-end test: full session flow (upload → chat → Feynman) | `chore` | manual QA | 📋 |
| 2 | Security review: role integrity, auth/JWKS, RLS **enforced via restricted role + `SET LOCAL`** (ADR-0009), key encryption, service-secret endpoints both directions, scope-lock (ADR-0002/0003/0008/0009/0011) | `chore` | `SECURITY.md` checklist | 📋 |
| 3 | Deploy FastAPI to Railway or Fly.io | `infra` | `Dockerfile`, Railway config | 📋 |
| 4 | Deploy frontend to Vercel | `infra` | Vercel project config | 📋 |
| 5 | Set all production environment variables | `infra` | Railway + Vercel dashboards | 📋 |
| 6 | Update CORS in FastAPI to production frontend URL | `chore` | `sensei-api/config.py` | 📋 |
| 7 | Smoke test on production URL | `chore` | manual QA | 📋 |

**Definition of Done:**
- [ ] FastAPI live and accessible at production URL
- [ ] Frontend live on Vercel
- [ ] Full session flow works on production
- [ ] No API keys or secrets in any public repository
- [ ] CORS locked to production frontend domain only

---

## Full Feature Checklist

- [ ] Session creation — Sprint 1/2
- [ ] Document upload and ingestion (RAG) — Sprint 3
- [ ] Scope auto-detection (document + first question) — Sprint 3/4
- [ ] Scoped Socratic chat (3 modes) — Sprint 4
- [ ] Out-of-scope redirect + 3-strike new session prompt — Sprint 4
- [ ] Feynman mode (7C's scoring + criticism) — Sprint 5
- [ ] Feynman retry flow — Sprint 6
- [ ] BYOK Gemini API key + Default Key & Daily Allowance — Sprint 2/4
- [ ] Upload cancellation — Sprint 3
- [ ] Session history on dashboard — Sprint 6
- [ ] Onboarding tour — Sprint 6
- [ ] All error states handled — Sprint 7
- [ ] Session expiry cleanup — Sprint 7
- [ ] Production deployment — Sprint 8
