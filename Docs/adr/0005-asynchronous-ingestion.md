# 0005 — Asynchronous ingestion with a Convex `documents` table

**Status:** Accepted

## Context

`/ingest/upload` accepts PDFs up to 5 MB and produces up to 200 embedded chunks. Doing that **synchronously** inside the HTTP request risks exceeding proxy/host timeouts (~30–60 s) on large files, leaving orphaned chunks and a stuck UI. The docs also contradicted themselves: ARCHITECTURE said synchronous ("returns ready", "no task queue") while API_CONTRACT and PRD implied async ("processing" status + a poll endpoint). And there was no table to hold per-document status.

## Decision

- **Ingestion is asynchronous.** `/ingest/upload` validates the cheap, upload-time guards (token, ≤5 MB file, ≤20 MB session, and *session not already at the 200-chunk cap*), creates a Convex `documents` row (`status: "processing"`), stores the raw PDF in Supabase Storage, returns `{ status: "processing", document_id }`, and runs the heavy work (extract → chunk → compact → *scope-gate (gated uploads only)* → cap-check → batch-embed → store chunks) in the background.
- **Status lives in a Convex `documents` table, not Supabase** — so the frontend gets live `processing → ready` updates via Convex's real-time subscriptions, no polling. Preserves the split: Convex owns metadata + sync; Supabase owns vectors + raw files.
- Background work sets `status: "ready"` (+ `chunkCount`) on success, or `"failed"` (+ `error`) on failure — **deleting any partial chunks** so a re-upload doesn't duplicate. A gated upload that fails the scope check (ADR-0011) sets `status: "rejected"` and likewise deletes its chunks + raw PDF.
- **Non-extractable PDFs fail fast.** If extraction yields negligible text (a scanned / image-only PDF → ~0 chunks after compaction), the document is set `status: "failed"` with a clear message ("Couldn't read text from this PDF — scanned or image-only documents aren't supported yet"). No OCR for MVP; it's the path to supporting scanned PDFs later.
- **Chunk-cap enforcement happens in the background, *after chunking and before embedding*** — the only point where the exact chunk count is known. The exact count can't be computed at upload (the PDF isn't extracted yet), so the upload-time check is only "is the session already at the cap?"; this is the authoritative gate. The pipeline is **compact → re-check → fail if still over**:
  - **Compact** (cheap, pre-embed): drop exact and near-duplicate chunks (text hashing / shingling — no embeddings needed) and obvious boilerplate (copyright/TOC/index/reference-list/running-header heuristics). This is a *standing ingestion-quality step* on every document — duplicates waste retrieval slots and skew similarity — not just an overflow rescue. It costs zero embedding spend and yields the exact post-compaction count.
  - **Re-check:** `existing session chunks + this document's post-compaction count` against the 200 cap.
  - **Fit → embed and continue. Still over → fail** the document (`status: "failed"` + clear "exceeds the 200-chunk session limit; upload a smaller excerpt or split it"), delete the raw PDF, write **no** chunks.
  - **Never truncate, and never prune *content* chunks for "usefulness."** Keeping the first 200 (or LLM-judging which content to drop) silently degrades RAG and the Feynman `Complete` criterion against material the student was never told is missing — betraying the "grounded in *your* materials" promise. Compaction removes *waste*; remaining overflow is genuine distinct content, and an honest failure beats silent loss.
- **`GET /ingest/status` is dropped;** the frontend subscribes to the `documents` table instead.
- **One operation per session at a time:** while a session has any document `processing`, `/chat/ask` is rejected server-side (and the client disables input), since RAG can't answer against half-loaded chunks.
- **Cancellable uploads:** the student can stop an in-progress upload. Cancellation is *cooperative* — BackgroundTasks can't be force-killed, so the worker checks an in-memory cancel signal (an `asyncio.Event` per `document_id`, set by `POST /ingest/cancel`) at checkpoints (after extraction, between embed batches) and aborts at the next one. On abort it hard-deletes the document's partial chunks + raw PDF and sets `status: "cancelled"`. Single-instance caveat matches BackgroundTasks; the signal moves to Convex/Redis when scaling out.
- For MVP the background work uses FastAPI **BackgroundTasks** (in-process, no separate queue); an instance restart loses in-flight jobs and the user re-uploads. A real queue (Arq/Celery + Redis) is the horizontal-scaling path.

## Consequences

- No HTTP timeout risk on large PDFs.
- New Convex `documents` table; `chunks.document_id` references it.
- Validation runs *before* the row is created (no orphaned "processing" rows); partial chunks are cleaned on failure.
- In-flight jobs are not durable on MVP — acceptable; re-upload recovers.
- `/chat/ask` rejects with `INGEST_IN_PROGRESS` while the session has a `processing` document — a server-side backstop behind the client-side input block.

## Considered alternatives

- **Synchronous ingestion:** simplest, but times out on exactly the large files the 5 MB limit allows. Rejected.
- **Status in Supabase:** works, but loses Convex's real-time push and forces frontend polling. Rejected.
- **A real task queue for MVP:** durable, but Redis + a worker is unjustified infra at MVP scale. Deferred to horizontal scaling.
- **Truncate to the first 200 chunks on overflow:** silent partial grounding — RAG and the Feynman `Complete` score judged against material with an unannounced hole. Rejected; an honest failure is better.
- **LLM-judge and prune "useless" content to fit:** a per-chunk generation pile (the cost ADR-0004 avoids), still probabilistic, and "useless" is an unknowable judgment about which chunk a future question needs. Rejected — it's truncation in disguise.
- **Semantic near-duplicate dedup (same idea, different words):** needs embeddings to detect, so it can't run pre-embed cheaply. Deferred; cheap *textual* dedup catches the common real cases (copy-pasted sections, repeated frontmatter).
