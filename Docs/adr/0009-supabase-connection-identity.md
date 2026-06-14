# 0009 — Supabase connection identity: restricted role + `SET LOCAL`, not the service key

**Status:** Accepted

## Context

DATABASE_SCHEMA defines per-user Row Level Security on the `chunks` table — policies that filter on `current_setting('app.current_user_id')` so a user only ever reads/writes/deletes their own chunks. Chunks are the **one** place another student's raw material physically lives (extracted PDF text + embeddings), so this is the most consequential confidentiality boundary in the system.

The obvious, default way to connect FastAPI to Supabase is the **service-role key**. But the service-role key **bypasses RLS entirely**. If FastAPI uses it, those policies are decorative: the only thing scoping chunks is the `WHERE user_id = …` clauses the application code remembers to write, with no database-level backstop. That:

- silently falsifies ADR-0008's load-bearing claim that cross-user isolation is **architectural, not coding-discipline** (the basis for dropping the injection blocklist);
- re-introduces exactly what ADR-0003 rejected — handing the most externally-exposed service (uploads, PDF parsing, Gemini calls) god-credentials to a data store;
- is *worse than no RLS*, because the visible-but-dead policies mislead future contributors into trusting a guard that isn't running.

Two surfaces don't fit the per-request-user mold and have to be reasoned about explicitly: the cron-triggered **cleanup** (ADR-0006), which acts on a `session_id` with no "current user," and **Storage** (raw PDFs), which lives in `storage.objects` and is not covered by the `chunks` policies.

## Decision

**Chunks — restricted role, RLS genuinely enforced.**
- FastAPI connects to Postgres as a **non-superuser role** that is *subject to* RLS (not the service-role key).
- Every request runs its `chunks` work inside a transaction that first does `SET LOCAL app.current_user_id = <verified userId>`. `SET LOCAL` is transaction-scoped, so it auto-resets on commit/rollback and cannot bleed across pooled connections — provided every query runs in a transaction and we use `SET LOCAL`, never bare `SET`, under a transaction-mode pooler (Supavisor).
- The `userId` is the one FastAPI already verified from the Convex JWT (ADR-0003) — never a client-supplied value.

**Cleanup stays on the same restricted role.** The hourly cleanup (ADR-0006) receives a `session_id`, looks up that session's owner, `SET LOCAL`s *that* `user_id`, then `DELETE … WHERE session_id = ?`. The owner's own delete policy permits it — no elevated DB credential needed.

**Storage — narrow service credential, MVP.** Raw-PDF upload and delete-on-expiry use a Supabase **Storage** credential, *not* the database service-role key. Blast radius is limited to the storage bucket (not the whole DB), the object paths are owner-derived and server-controlled, and PDFs are hard-deleted on expiry anyway. RLS-scoping `storage.objects` is deferred — a follow-up when convenient, not MVP.

## Consequences

- A FastAPI bug that forgets a `WHERE user_id` clause on `chunks` returns nothing — the database filters by `app.current_user_id`. The architectural-isolation claim in ADR-0008 is now actually true at the DB layer.
- A FastAPI compromise cannot read or wipe arbitrary `chunks`: the restricted role only ever sees the user whose id is in the current transaction's GUC. The Postgres service-role key is **never** placed in FastAPI's environment.
- New ops requirement: a dedicated restricted Postgres role with `SELECT/INSERT/DELETE` on `chunks` and permission to set the `app.current_user_id` GUC; its DSN is the connection string FastAPI holds (not the service key).
- Discipline the code must keep: all `chunks` access is wrapped in a transaction with `SET LOCAL` first. A bare `SET` (session-scoped) under a transaction-mode pooler would leak the GUC to the next checkout — explicitly forbidden.
- The Storage credential is a separate, narrower secret. The DEPLOYMENT secrets matrix lists **two** Supabase entries — the restricted-role DSN and the Storage credential — not one service key.
- Storage objects are not RLS-isolated on MVP; their protection is server-controlled, owner-derived paths plus the fact that no route hands a client a raw Storage handle. Flagged for later hardening.

## Considered alternatives

- **Service-role key for everything (the default):** simplest, but bypasses RLS, makes the `chunks` policies theater, contradicts ADR-0008's isolation claim, and gives the most-exposed service god-credentials to the DB. Rejected.
- **Delete the RLS policies and rely on app-level scoping only:** at least honest, but throws away a free database-level backstop on the highest-stakes table. Rejected.
- **RLS-scope Storage too, on MVP:** the consistent end state, but more setup (`storage.objects` policies + signed access) than MVP warrants given the narrow, server-controlled access pattern. Deferred, not rejected.
