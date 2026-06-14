# 0006 — Session expiry: Convex cron drives a single clock; FastAPI deletes Supabase

**Status:** Accepted

## Context

Sessions expire after 3 days of inactivity (PRD F1): Supabase hard-deletes chunks + raw PDFs; Convex keeps the session row (→ `expired`), chat history, and Feynman scores for read-only history. Two gaps:

1. No doc named **what runs the deletion** — and it spans Convex (which owns the inactivity clock) and Supabase (which holds the data).
2. The schema had **two expiry clocks** — `sessions.lastActivityAt` (moves with activity) and `chunks.expires_at` (written once at upload). They drift: a still-active session's chunks can have a long-passed `expires_at`, so any sweep on that column would delete documents out from under an active session.

## Decision

- **Single clock:** `sessions.lastActivityAt` (Convex), bumped on a chat message, a Feynman submission, or a document upload. Viewing history does **not** extend it. `chunks.expires_at` and its index are **dropped**.
- **Convex cron (hourly)** finds `status:"active"` sessions with `lastActivityAt < now − 3 days` and, per session, calls a **service-secret-protected FastAPI internal cleanup endpoint**.
- **FastAPI cleanup** deletes all of the session's chunks (incl. the scope anchor) from pgvector and all raw PDFs from Supabase Storage (via `documents.storagePath`). Idempotent — re-running on already-clean data is a no-op.
- Convex sets `session.status:"expired"` **only after** cleanup succeeds; a partial failure leaves it `active` for the next run to retry. Eventual, retry-safe consistency.
- **Kept indefinitely:** session row, `messages`, `feynmanScores`, and `documents` metadata rows (lightweight; power read-only history). **Deleted:** chunks + raw PDFs.
- **Expired sessions are read-only:** `/chat/ask`, `/ingest/upload`, and `/evaluate/feynman` reject when `status:"expired"`.

## Consequences

- One clock removes the drift bug; cleanup is owned by the only service with Supabase credentials (FastAPI) and triggered by managed Convex cron (independent of FastAPI instance count).
- `documents` rows outlive their files (`storagePath` becomes a tombstone) — acceptable for history; the gone-ness is implied by `status:"expired"`.
- Adds a **Convex → FastAPI** internal endpoint (the reverse of ADR-0003's FastAPI → Convex path), protected by a shared service secret.
- **This endpoint is "internal" by purpose, not by network.** Convex cron runs on Convex's cloud, so it reaches FastAPI over the public internet — the route must be **publicly reachable** (behind the TLS proxy), gated *only* by `CONVEX_SERVICE_SECRET`. Firewalling it to a private network silently breaks expiry (Supabase fills up, no error surfaces). Because a leaked secret lets a caller force-expire **any** session by id — targeted chunk/PDF destruction, not just disclosure — the secret comparison must be constant-time, and the endpoint stays idempotent so replays are no-ops. Deployment wiring is captured in DEPLOYMENT.md.
- Read-only enforcement implies a `SESSION_EXPIRED` error on the three AI routes (not yet added to the contract).

## Considered alternatives

- **FastAPI scheduler:** reuses the existing secret, but needs an in-app scheduler plus a lock to avoid double-runs across instances. Rejected for MVP simplicity vs Convex's managed cron.
- **Supabase `pg_cron` on `expires_at`:** can't touch Storage or the Convex status, and *is* the drift bug. Rejected.
- **Lazy / on-access expiry:** never frees Supabase space for simply-abandoned sessions (the common case). Rejected.
