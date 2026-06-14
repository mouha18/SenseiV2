# 0011 — Scope locks at first interaction; later uploads are scope-gated, not scope-deriving

**Status:** Accepted

## Context

ADR-0004 said the scope anchor is "the document chunks when documents exist, otherwise the embedded scope description." That rule is only well-defined when documents are known **at derivation time**. But a session can interleave chat and uploads: a student can ask a question first (deriving a description anchor) and *then* upload a PDF — or upload, then later upload another. The original rule doesn't say what the anchor is when documents arrive **second**, and it leaves "can you even add documents mid-session?" unanswered. We considered locking uploads to session-start to dodge this, but the product wants a student to be able to bring in material as a study session develops.

## Decision

**Scope is derived exactly once — at the session's first interaction — and never moves.**

- **Lock event:** the first interaction sets the scope and the anchor. *Upload-first* → scope label + chunk anchor derived from the documents (ADR-0004). *Chat-first* → scope label + description embedding derived from the first question (ADR-0004). The first interaction can never be "out of scope" — it *defines* scope.
- **The anchor is frozen at its lock type.** Chat-first sessions enforce scope against the **description embedding** (`SCOPE_THRESHOLD_DESC`) for the life of the session; document-first sessions enforce against the **chunk anchor** (`SCOPE_THRESHOLD_DOC`). This does **not** change when documents arrive later.

**Later uploads never re-derive the scope — they are gated against the locked anchor**, the document analogue of the per-message scope gate:

- In a **document-locked** session, upload #1 *derives*; uploads #2+ are *gated*. In a **chat-first** session, **every** upload is gated.
- **The document scope gate** (in the background ingestion pipeline, ADR-0005): extract → chunk → **compact** (ADR-0005) → **embed a bounded sample** of the compacted chunks → compare the sample to the locked anchor → gate **before** embedding the remainder.
  - **Aggregate = median / quorum of the sample**, not top-1. A document must be *substantially* on-topic; top-1 would let a mostly-off-topic PDF pass on a single stray chunk (a "Disco's history" file that mentions a war once).
  - **In-scope →** embed and store the remaining chunks; they join the session's **RAG retrieval pool** (retrieval material only — they improve answers and Feynman grounding but **do not become or alter the anchor**).
  - **Out-of-scope →** reject: delete the document's chunks + raw PDF, set `documents.status: "rejected"`, and surface an upload-redirect message ("Let's keep this session on <scope> — that document is off-topic"). No embedding is spent on the rejected remainder.
- **Out-of-scope uploads are a separate path from the 3-strike question counter.** They do **not** increment `sessions.outOfScopeCount` (which exists for *conversational* drift). Dragging in the wrong PDF should not push a student toward a new-session prompt.

## Consequences

- One iron rule replaces the ambiguous "anchor = chunks if docs exist": **scope is set once, at first interaction, and nothing later moves it.**
- A chat-first session that later gains in-scope documents enforces scope against its original **description** even though chunks now exist — the chunks are retrieval-only. (Frozen anchor; corrects ADR-0004.)
- Feynman's "Correct/Complete judged against documents when present" (ADR-0007) keys on *"any retrievable chunks exist,"* independent of anchor type — so a chat-first session with later in-scope uploads is graded against those docs. Consistent.
- The document gate adds a **sample-embed + comparison** step for gated uploads — mirrors the #4 compact-then-gate cost pattern, and spends **no Gemini generation call** (no label-derivation).
- **New tuned knob:** the document-gate threshold compares *chunk-sample → anchor*, a different distribution from the per-message *question → anchor* gate, so it needs its own calibration (a chat-first gate compares doc chunks to a description; a doc-locked gate compares new chunks to existing chunks). Seeded from the ADR-0004 thresholds, tuned separately.
- **Forced edits:** `documents.status` gains a `"rejected"` value (DATABASE_SCHEMA, ADR-0005, API_CONTRACT ingestion section); ADR-0004 gets a pointer + the frozen-anchor correction; CONTEXT.md's **Scope anchor** definition is rewritten around "first interaction," and an **Out-of-scope upload** term is added.
- Because the lock is irreversible for the session's life, scope **derivation surfaces a confirmation gate** ("Start" / "Re-detect") *before* locking (PRD F1) — a wrong scope is caught up front rather than after three redirects. No in-session scope editing for MVP (impossible for a chunk anchor anyway); a wrong scope discovered later is recovered by starting a new session.

## Considered alternatives

- **Lock uploads to session-start only:** simplest (no document gate at all), but a student can't bring in material as a study session develops. Rejected for inflexibility.
- **Re-derive / switch the anchor to chunks when documents arrive later:** violates "scope set once" — a later upload could silently shift the topic boundary out from under earlier messages. Rejected.
- **Derive a one-line document summary via Gemini and embed *that* for the gate:** one generation call per upload (and an allowance question); the sample-embed gate is cheaper and reuses the embedding path. Rejected.
- **Top-1 aggregation for the document gate** (as the per-message gate uses): lets a mostly-off-topic document pass on a single matching chunk. Rejected for median/quorum — a document should be on-topic *as a body*, not by a stray sentence.
