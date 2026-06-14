# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project state

**This repo is design-complete but pre-code.** As of the last update no application code exists — only the documentation bundle in `Docs/`, the `CONTEXT.md` domain glossary, and a throwaway calibration spike in `calibration/`. The build follows `Docs/IMPLEMENTATION_ROADMAP.md` foundation-first: **Sprint 1 (scaffold + Convex schema + Supabase pgvector + FastAPI `/health`)** is the next step, then Sprint 2 auth, then the FastAPI RAG/chat/Feynman pipeline. When you scaffold, create `frontend/` (Next.js) and `sensei-api/` (FastAPI) per the structure in `Docs/README.md`.

## What Sensei is

A Socratic study tutor: students upload course PDFs (or not) and learn through guided dialogue grounded in those materials via RAG, then test understanding with Feynman-style self-explanation scoring. Read `CONTEXT.md` first — it is the authoritative domain glossary (BYOK, Daily Allowance, Scope anchor/derivation/enforcement, Question/Response modes, 7C's). Use those exact terms; the glossary lists deprecated synonyms to avoid (e.g. "platform key", "quota", "subject").

## Split-backend architecture

Four services, each with one job (`Docs/ARCHITECTURE.md` has the full diagram and data flows):

- **Next.js frontend** — UI only. Talks to Convex for data (real-time subscriptions) and to FastAPI for AI operations.
- **FastAPI (`sensei-api/`)** — *all* AI logic: ingestion, embedding, retrieval, Gemini calls, scope enforcement, Feynman scoring. Routers are thin; logic lives in `services/`.
- **Convex** — auth, session metadata, chat history, Feynman scores, velocity/allowance counters, cron. Source of real-time sync.
- **Supabase** — pgvector chunk+embedding storage and raw PDF file storage, with RLS.

Critical boundary rules:
- **Messages and Feynman scores are written server-side by FastAPI** via purpose-built Convex service endpoints (`persistTurn`, `persistFeynman`), authenticated with a shared service secret — **the client never writes them and sends no conversation history** (ADR-0010). The chat pipeline order is fixed: velocity → scope → allowance → Gemini → persist (refund allowance on Gemini failure).
- FastAPI verifies the Convex auth token on every non-health route via **offline JWKS verification + a `tokensValidAfter` check** (ADR-0003) — not a network call per request.
- FastAPI connects to Supabase as a **restricted (non-superuser) role** and sets `app.current_user_id` via `SET LOCAL` so RLS is enforced in-database (ADR-0009) — not via the service key.

## Non-obvious domain rules (read the ADR before touching these)

Decisions are recorded in `Docs/adr/` and are binding — honor them, don't re-derive them.

- **`Docs/PROMPTS.md` is the single source of truth for every LLM prompt** (chat system prompt, scope-judge, topic derivation, Feynman scorer, concept suggestion). Port prompts from there verbatim; do not invent them.
- **Models:** embeddings use `gemini-embedding-001` at **1536 dims** (MRL-normalized, L2-normalized before cosine; `text-embedding-004` is dead). Chat and scorer use `gemini-3.1-flash-lite`.
- **Scope gating uses a band + un-metered LLM scope-judge in BOTH modes — there is no single fixed threshold** (ADR-0004 + its amendment, proven by `/calibration`). Doc sessions: top-1 chunk sim ≥0.66 in / ≤0.59 out / **0.59–0.66 → LLM judge**. Doc-less: question-vs-description ≥0.63 in / ≤0.57 out / **0.57–0.63 → LLM judge**. Clear-in/clear-out are decided in code with no Gemini call. **These band edges are provisional (8 synthetic topics) and must be re-calibrated on real traffic before launch.**
- **The scope anchor is fixed at the session's first interaction and never moves** (ADR-0011): the uploaded chunks if the session began with an upload, else the embedded scope description from the first question. Documents added later are retrieval material only.
- **Daily Allowance counts delivered answers, not attempts** — errors/timeouts/safety-blocks are refunded; out-of-scope redirects and embeddings never count (ADR-0001). Velocity limit is 20/min, a fixed window on the Convex `users` row.
- **Feynman `overall_score` is the six-C average with Courteous excluded**, computed in code (ADR-0007).
- **Role integrity is enforced by a role-locked system prompt + the scope gate — no keyword blocklist** (ADR-0008).
- Ingestion is async (FastAPI BackgroundTasks); document status (`processing`/`ready`/`failed`/`cancelled`/`rejected`) is observed via the Convex `documents` subscription — there is no status endpoint (ADR-0005).

## Commands

No app build/lint/test exists yet. Per `Docs/CONTRIBUTING.md`, once scaffolded:

```bash
# Frontend (frontend/)
npm run dev
npm run lint && npm run typecheck

# FastAPI (sensei-api/)
uvicorn main:app --reload
ruff check . && mypy .
```

The **calibration spike** is the only runnable code today (throwaway — delete once thresholds are locked into ADR-0004 and `config.py`):

```bash
cd calibration
# PowerShell: $env:GEMINI_API_KEY="your-key"
python scope_calibration.py            # single-topic
python scope_calibration_expanded.py   # multi-topic generalization check
```

## Code standards (from CONTRIBUTING.md)

- Thin FastAPI routers — no business logic in handlers; delegate to `services/`.
- Pydantic models for every request; `async/await` for all external calls (Gemini, Supabase, embeddings).
- TypeScript strict mode; no unjustified `as` assertions.
- Never write to Convex from FastAPI except through the designated service endpoints.
- Conventional commits (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`), ≤72-char subject. Branch off `dev` (`feat/*`, `fix/*`); never commit to `main` directly.
