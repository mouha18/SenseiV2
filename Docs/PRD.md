# PRD — Sensei

**Version:** 1.0
**Status:** Draft
**Last Updated:** 2026-06-10
**Author:** Mouhamed (Pikou)

---

## 1. Problem Statement

Students who rely on passive learning tools — search engines, chatbots that answer directly — build surface-level understanding. They can retrieve information but cannot explain or apply it. When exam time comes or real-world application is required, the knowledge isn't there.

Existing AI tools like ChatGPT answer every question directly, which bypasses the cognitive effort needed for genuine retention. There is no tool that actively trains a student to think, not just consume.

---

## 2. Product Vision

In 12 months, Sensei is the go-to study companion for university students who want to genuinely own their material — not just pass exams. A student uploads their course PDFs, has a Socratic dialogue grounded in their own materials, and walks away able to explain every concept they studied. Feynman scores become a personal metric of mastery tracked across sessions.

---

## 3. Target Users

### University Student (Primary)
- **Who:** 18–25, studying any discipline, owns course PDFs
- **Goal:** Understand material deeply, not just memorize it
- **Pain point:** Passive reading and ChatGPT answers don't build real understanding

### Self-learner (Secondary)
- **Who:** Anyone learning a topic independently, no formal course materials
- **Goal:** Guided exploration of a subject with structured feedback
- **Pain point:** No accountability or structure when learning alone

---

## 4. User Stories

### P0 — Must have for MVP

- As a student, I want to start a study session and upload my course PDFs so that Sensei can answer questions grounded in my materials.
- As a student, I want Sensei to guide me with questions instead of giving me direct answers so that I build real understanding.
- As a student, I want Sensei to answer directly when I ask a factual question so that I'm not frustrated by unnecessary Socratic loops.
- As a student, I want the session to stay on topic so that I'm not distracted by unrelated conversations.
- As a student, I want to trigger Feynman mode and explain a concept so that I can measure how well I actually understand it.
- As a student, I want to receive a score and detailed criticism on my Feynman explanation so that I know exactly where my understanding is weak.
- As a student, I want to use my own Gemini API key so that I control my own usage and costs.
- As a student, I want my session history and Feynman scores saved so that I can track my progress over time.

### P1 — Important but not blocking MVP

- As a student, I want an onboarding tour on first login so that I understand how to use Sensei effectively.
- As a student, I want to retry a Feynman explanation after receiving criticism so that I can improve in the same session.
- As a student, I want Sensei to confirm the session topic when I upload documents so that I know the scope is correctly detected.
- As a student, I want to see a history of all past sessions so that I can revisit previous study material.

### P2 — Nice to have post-MVP

- As a student, I want to see my Feynman score history per concept across sessions so that I track mastery over time.
- As a student, I want Sensei to suggest related concepts to explore after a session so that I discover gaps I didn't know I had.

---

## 5. Feature Specifications

### F1 — Session Management
**Priority:** P0
**Description:** A session is the unit of study. It has a scope (topic), optional uploaded documents, a chat history, and Feynman scores. Sessions expire after 3 days of inactivity.
**Acceptance Criteria:**
- [ ] Student can start a new session from the dashboard
- [ ] Session scope is auto-detected from uploaded documents or first question
- [ ] Sensei confirms the topic at session start as an explicit gate, not a passive toast — the detected scope is shown with "Start" (locks it) vs "Re-detect" (re-derives) — so a wrong scope is caught before it locks (ADR-0011). No in-session scope editing for MVP; if a wrong scope is found later, a new session is the recovery
- [ ] Session data persists in Convex; document chunks persist in Supabase
- [ ] After 3 days of inactivity (Convex cron, off `lastActivityAt`), Supabase chunks + raw PDFs are hard-deleted and the session is marked `expired` (ADR-0006)
- [ ] Expired sessions are read-only: chat history + Feynman scores remain; new messages/uploads/Feynman are rejected

### F2 — Document Ingestion (RAG)
**Priority:** P0
**Description:** Student uploads PDFs at session start. FastAPI extracts text, chunks it with overlap, embeds each chunk, and stores vectors in Supabase scoped to the session and user.
**Acceptance Criteria:**
- [ ] Accepts PDF files up to 5MB per file
- [ ] Rejects uploads exceeding 20MB total per session
- [ ] Max 200 chunks stored per session
- [ ] Chunks are scoped to user_id and session_id
- [ ] Ingestion status visible to student (processing / ready / failed / cancelled)
- [ ] Student can cancel an in-progress upload; the document's partial chunks and raw PDF are hard-deleted (ADR-0005)
- [ ] While a document is processing, chat input is blocked (client) and `/chat/ask` is rejected server-side (ADR-0005)
- [ ] Documents optional — session works without them

### F3 — Scoped Socratic Chat
**Priority:** P0
**Description:** Three-mode response system. Conceptual questions get Socratic guidance (max 1 exchange before direct answer). Factual questions get direct answers. Application questions get Socratic guidance. All questions checked against session scope before processing.
**Acceptance Criteria:**
- [ ] Scope check runs on every message after the first
- [ ] Out-of-scope message returns a gentle redirect
- [ ] After 3 consecutive out-of-scope messages, student is prompted to start a new session on that subject
- [ ] Conceptual questions: Sensei asks a guiding question first
- [ ] If student still doesn't understand after one Socratic exchange, direct answer given
- [ ] Factual questions: answered directly with no Socratic loop
- [ ] Application questions: Sensei guides student to reason through it
- [ ] RAG retrieval attempted first if documents exist; falls back to general knowledge if no relevant chunks found
- [ ] Velocity rate limit: 20 requests per minute per user (anti-abuse; applies to everyone, including BYOK)
- [ ] Daily Allowance: 20 Gemini generation calls per day per user on the Default Key — chat answers and Feynman evaluations both count (cost cap; resets at UTC midnight; lifted under BYOK — see F4, F5, ADR-0001)
- [ ] When the Daily Allowance is exhausted, the student is prompted to add their own Gemini key rather than blocked outright

### F4 — Feynman Evaluation Mode
**Priority:** P0
**Description:** Student clicks "Test Me", picks a concept (typed freely, or chosen from Sensei's suggestions drawn from the session discussion), explains it in their own words, and receives a structured score across the 7C's of communication with detailed per-criterion criticism.
**Acceptance Criteria:**
- [ ] "Test Me" button available at all times during a session
- [ ] Student is asked which concept they want to explain via a form: they can type their own concept, or pick from 3–5 concepts Sensei suggests based on the session discussion (concept suggestion drawn from the conversation — pulled forward from P2)
- [ ] The concept-suggestion call is **un-metered** — it does not count against the Daily Allowance (it's a helper, not a graded evaluation; cost bounded by the velocity rate limit — ADR-0007, ADR-0001)
- [ ] Student submits free-form explanation
- [ ] Score returned for each of the 7C's: Clear, Concise, Concrete, Correct, Coherent, Complete, Courteous
- [ ] Overall Feynman score returned
- [ ] Detailed criticism per criterion returned
- [ ] Student offered to retry or continue chatting
- [ ] Result persisted: concept name, raw explanation, per-criterion scores, overall score, timestamp
- [ ] Scores calibrated for run-to-run consistency (anchored rubric + graded examples + near-zero temperature); overall is the average of the six understanding criteria — Courteous is scored and shown but excluded from the overall (ADR-0007)
- [ ] Correct/Complete judged against the student's documents when present, else scoped general knowledge (ADR-0007)
- [ ] Each evaluation, including retries, counts as one generation call against the Daily Allowance (ADR-0007)

### F5 — Key Model: Default Key + BYOK
**Priority:** P0
**Description:** Sensei runs on a **Default Key** (the platform owner's Gemini key, held in the FastAPI environment) by default, bounded by a **Daily Allowance** that caps the platform owner's cost. A student may optionally provide their own Gemini key (**BYOK**); their key is stored encrypted and used for all their Gemini calls, lifting the Daily Allowance. See [ADR-0001](./adr/0001-default-key-daily-allowance-byok.md).
**Acceptance Criteria:**
- [ ] Students without a saved key use the Default Key, subject to the Daily Allowance (see F3)
- [ ] Student can input their own Gemini API key in settings
- [ ] Key stored encrypted in Convex
- [ ] Key validated before saving (test call to Gemini)
- [ ] When a student has a saved key, all their Gemini calls use it (BYOK) and the Daily Allowance no longer applies
- [ ] Student can update or delete their key at any time (deleting reverts them to the Default Key + Daily Allowance)

### F6 — Session History
**Priority:** P1
**Description:** All past sessions visible on the dashboard, sorted by most recent activity, with topic, date, status, and a Feynman summary.
**Acceptance Criteria:**
- [ ] Dashboard lists all sessions sorted by last activity (most recent first), each with scope label, date, and an Active/Expired status badge
- [ ] Each card shows a Feynman summary: best overall score + attempt count (e.g. "Best 82 · 3 attempts")
- [ ] Reopen: Active sessions resume (chat enabled); Expired sessions open read-only (history + Feynman results visible, input disabled — `SESSION_EXPIRED`)
- [ ] Empty state shows a "Start your first session" CTA

---

## 6. Out of Scope (v1)

- Multi-user collaboration or shared sessions
- Audio or video input
- Mobile app (web only for MVP)
- Stripe or any payment integration
- Custom AI model selection beyond Gemini
- Notifications or email digests
- Export of session transcripts

---

## 7. Success Metrics

| Metric | Target | How to Measure |
|---|---|---|
| Sessions created | 50 in first month | Convex session count |
| Feynman attempts per session | ≥ 1 | Convex Feynman score records |
| Average Feynman overall score | > 60/100 | Aggregated score data |
| Out-of-scope redirect rate | < 10% of messages | FastAPI scope check logs |
| Document upload rate | > 60% of sessions | Convex session metadata |

---

## 8. Timeline & Milestones

| Milestone | Target Date | Deliverable |
|---|---|---|
| Architecture + docs complete | Week 1 | This bundle |
| FastAPI skeleton + RAG pipeline | Week 2–3 | Ingest + retrieval working |
| Convex schema + auth | Week 2 | Auth, session, history working |
| Chat route + Socratic logic | Week 3–4 | Full chat loop working |
| Feynman mode | Week 4–5 | Evaluation flow working end-to-end |
| Frontend (Next.js) | Week 5–6 | Full UI connected to backend |
| Testing + polish | Week 7 | Error states, edge cases handled |
| Deployed MVP | Week 8 | Live, shareable URL |

---

## 9. Open Questions

- [x] What embedding model specifically? → Google `gemini-embedding-001`, MRL-truncated to **1536 dimensions** (fits pgvector's 2000-dim index cap on the standard `vector` type). Same API key as Gemini, guarantees vector-space consistency between document chunks and query embeddings. (Supersedes `text-embedding-004`, retired Jan 14 2026.)
- [x] Session expiry: soft-delete or hard-delete from Supabase? → Hard delete. Supabase chunks and raw PDFs are permanently deleted on expiry. Convex chat history and Feynman scores are kept indefinitely (lightweight, useful for history).
- [x] Onboarding tour: built custom or using a library? → Shepherd.js. Shown once on first login (tracked by `users.onboardedAt`); a non-blocking, skippable overlay; not replayable for MVP.
- [ ] Error state designs for each failure scenario (deferred to frontend stage)
