# 0004 — Scope by embedding gate; classification folded into the answer call

**Status:** Accepted

## Context

Every chat message must be checked against the session's scope (PRD F3), and in-scope questions classified as conceptual / factual / application to choose a Socratic vs direct reply. Both are semantic judgments, which *naively* implies one or two Gemini calls per message — **including on out-of-scope messages** — multiplying latency, spending the Default Key's budget (ADR-0001) on messages that produce no answer, and potentially consuming the student's Daily Allowance for nothing.

## Decision

Separate scope **derivation** (once) from scope **enforcement** (per message).

**Scope derivation — once, at the first message:**
- *Doc-less:* one Gemini call (the topic-confirmation call PRD F1 already requires) draws a scope **label** + a short **description**. Label → `sessions.scope`; description is embedded and stored as the **scope anchor**.
- *Doc sessions:* the label is derived from the uploaded documents at ingestion; the document chunks themselves are the anchor.

**The anchor is fixed at this first derivation and never moves — see [ADR-0011](./0011-scope-locks-at-first-interaction.md).** Whichever interaction comes first (an upload or the first question) locks the anchor *type*; documents uploaded *later* are scope-**gated** against that anchor (out-of-scope uploads are rejected and their chunks/PDF deleted) and join the retrieval pool as material only — they do **not** re-derive or switch the anchor. So "anchor = chunks if documents exist" holds only for document-*first* sessions; a chat-first session keeps its description anchor even after in-scope documents are added.

**Scope enforcement — every later message, in FastAPI (not the prompt):**
- Embed the question (the same embedding feeds RAG retrieval when documents exist).
- Cosine similarity vs the anchor, compared to a threshold **in Python**. The anchor differs by session type, so the measurement — and the threshold — differ too:
  - *Doc sessions:* reuse the RAG vector search; the scope signal is the **top-1 (best-matching) chunk's** cosine similarity, compared to `SCOPE_THRESHOLD_DOC`. Top-1 (not a top-k mean) so a legitimately narrow question touching a single passage isn't rejected by averaging in distant chunks. Costs no extra vectors — it is a byproduct of retrieval, and the same retrieved chunks feed the in-scope answer call.
  - *Doc-less sessions:* cosine similarity vs the single embedded scope **description**, compared to `SCOPE_THRESHOLD_DESC`.
- **Below threshold → out of scope:** return a templated redirect, increment `sessions.outOfScopeCount` in Convex (3 consecutive → new-session prompt). **No Gemini call; does not consume the Daily Allowance.**
- **At/above threshold → in scope:** reset the counter; make **one** Gemini call that classifies the question and answers in the right mode (factual → direct; conceptual/application → Socratic), returning JSON `{ answer, responseType, source }`. Counts as 1 against the allowance.
- The first message *sets* the anchor and is not scope-checked.

**Socratic exchange cap (PRD F3 — at most one guiding question):**
The in-scope answer call chooses Socratic vs direct **deterministically** from the previous assistant message's `responseType`: if the last reply was `socratic`, this turn gives the **direct** answer (the one-round cap is reached); otherwise normal classification applies. This is a *count*, not a semantic judgment — no similarity check. The signal rides on `conversation_history` (each item carries its `responseType`), so it needs no extra Gemini call and no extra stored state. Client-supplied `responseType` is trusted here: spoofing it only denies the student their own guiding question, with no security impact.

## Rationale

- The threshold comparison is deterministic and belongs in code — LLMs are unreliable at numeric comparison, and gating in code means out-of-scope messages never reach Gemini (zero generation cost, zero allowance burn).
- Folding classification into the answer call removes a second per-message LLM call.
- Embedding the Gemini-drawn **description** (not the raw first question) gives a richer, more reliable anchor for doc-less sessions.

## Consequences

- Out-of-scope = one cheap embedding, no generation call. In-scope = one embedding + one generation call.
- **Embeddings are deliberately un-metered** (excluded from the Daily Allowance): an out-of-scope message still gets embedded to *know* it's out of scope, and the 3-strikes response is a prompt, not a block, so a student can keep firing off-topic. The embedding spend on the Default Key is therefore bounded only by the **velocity rate limit (20/min, ADR-0001)** — which is acceptable because `text-embedding-004` is free-tier-cheap, and a harder block can't work (you must embed to detect a return to scope, so freezing a "stuck" session would break legitimate recovery). The velocity limit *is* the embedding-cost backstop.
- **Storage:** the doc-less scope description needs a stored embedding → kept in Supabase as a chunk flagged `is_scope_anchor` (excluded from RAG retrieval); the description text is kept in Convex `sessions.scopeDescription`.
- Enforcement quality depends on **two** tuned thresholds — `SCOPE_THRESHOLD_DOC` (top-1 chunk similarity) and `SCOPE_THRESHOLD_DESC` (description similarity). They sit in **different score distributions** — similarity to a one-line abstract summary vs to the single best-matching page of raw text — so one shared number misfires in one mode. Each is calibrated **separately**, against a handful of known in-/out-of-scope questions per mode; this calibration is real work, not a guessed constant. If a tuned threshold still misbehaves, an LLM scope-judge can be added later **for borderline-similarity cases only**.
- `outOfScopeCount` is owned by Convex; the client no longer supplies it (API contract updated).

## Considered alternatives

- **LLM scope-judge on every message:** more robust semantically, but a Gemini call per message (out-of-scope included) with added latency. Rejected for cost/latency.
- **Pass the score + threshold to Gemini and let it decide:** unreliable (LLM arithmetic) and still pays for out-of-scope. Rejected.
- **Separate classification call:** an extra per-message call; folded into the answer call instead.
- **Embed the bare first question as the doc-less anchor:** noisier; rejected in favour of embedding a drawn description.

## Calibration & amendment (2026-06-13; expanded 2026-06-14)

Thresholds were calibrated with a throwaway embedding spike (`/calibration`) against the production embedding model. Two findings change this ADR:

**Embedding model corrected.** `text-embedding-004` (named in PRD/README) was retired Jan 14 2026. Replaced by **`gemini-embedding-001`**, MRL-truncated to **1536 dims** (fits pgvector's 2000-dim index cap on the standard `vector` type). All thresholds below are relative to this model + dimension; anchors embed as `RETRIEVAL_DOCUMENT`, questions as `RETRIEVAL_QUERY` (production must match, or the numbers don't transfer).

**Both per-message gates use a band + LLM scope-judge — neither mode separates on a fixed threshold.** A first pass (4 clean topics) suggested doc sessions separated cleanly at ~0.64 while doc-less (DESC) did not. An **expanded pass (8 subjects incl. same-domain pairs — photosynthesis/respiration, French-Revolution/WWII, derivatives/linear-algebra — and realistic terse phrasing)** overturned the DOC result: a fixed 0.64 produced 7 errors (e.g. "role of ATP in the Calvin cycle" matched the *respiration* chunks at 0.656; "who was Hitler" fell to 0.601 against its own chunks). Adjacent topics share vocabulary, and terse name-questions match prose chunks weakly — so **no fixed threshold cleanly gates either mode.** (For DESC the same pass also confirmed enriching the anchor — centroid of description + sample questions, or `SEMANTIC_SIMILARITY` task type — makes it *worse*, gaps −0.025 to −0.044: the overlap is irreducible at the summary level.) This is the LLM-judge escape hatch this ADR anticipated, now extended to **both** modes.

The gate is uniform: similarity routes to **clear-in / clear-out / judge**, with per-mode band edges (calibrated on 8 topics — *zero clear-zone errors*, i.e. no in-scope question in the clear-out zone or vice-versa; ~5–6% of messages reach the judge):
- **Doc sessions:** ≥ 0.66 in · ≤ 0.59 out · **0.59–0.66 → judge**, grounded in the scope label + the top retrieved chunks.
- **Doc-less sessions:** ≥ 0.63 in · ≤ 0.57 out · **0.57–0.63 → judge**, grounded in the scope label + description.

Clear-in/clear-out decide **in code with no Gemini call** (preserving "out-of-scope spends nothing"); only the borderline band invokes the **LLM scope-judge** (`gemini-3.1-flash-lite`, MINIMAL thinking, temp ~0, structured `{ inScope: boolean }`). The judge is **un-metered** (a routing helper, like embeddings — ADR-0001), bounded by the velocity rate limit and by the band being a small minority of messages. Prompt in `PROMPTS.md` §5.

All numbers rest on `gemini-embedding-001` @ 1536 dims, anchors as `RETRIEVAL_DOCUMENT` and questions as `RETRIEVAL_QUERY` (production must match or they don't transfer). Band edges are **provisional** — validated on 8 synthetic topics, not real traffic; the chat route should log every scope decision `(question, similarity, in/out, judge verdict)` so the bands re-tune on real questions post-launch.
