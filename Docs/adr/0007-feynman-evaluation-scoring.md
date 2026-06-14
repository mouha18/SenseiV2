# 0007 — Feynman evaluation: calibrated 7C's scoring

**Status:** Accepted

## Context

F4 scores a student's free-form explanation across the **7C's** (Clear, Concise, Concrete, Correct, Coherent, Complete, Courteous) with per-criterion criticism and an overall score, persisted per attempt. The docs named *"a 7C's rubric prompt"* but defined neither the rubric, nor how to keep LLM scores stable, how Correct/Complete are judged, or how to stop gaming — all of which decide whether the score means anything (it's also a tracked success metric).

## Decision

**Consistency**
- **Coarse anchored rubric** — per criterion, a definition + low/mid/high reference points; output is 0–100. (Fine 10-point bands rejected: LLMs wobble between adjacent fine bands, *increasing* drift.)
- **~4–5 hardcoded graded example explanations** spanning quality archetypes (incoherent/vague, verbose-but-correct, copied-verbatim → low, partially-correct-with-gaps, excellent). Same set every call; they anchor the *scale*, which is topic-agnostic.
- **Near-zero temperature** + **forced JSON** output schema.
- **`overall_score` computed in code** as the equal-weighted average of the **six understanding-bearing** sub-scores — Clear, Concise, Concrete, Correct, Coherent, Complete — **excluding `Courteous`** (not emitted by Gemini). `Courteous` is still scored and shown as per-criterion feedback, but tone is not understanding, and the overall is a *mastery* metric (PRD F4, tracked as a success KPI), so a blunt-but-correct explanation should not be marked down on mastery. Excluding the one off-axis criterion keeps the overall a pure understanding signal while staying code-computed and transparent ("the average of the six understanding criteria"). A UI caption notes that Courteous is feedback-only, so a low Courteous not moving the overall isn't surprising.

**Ground truth for Correct/Complete**
- **Doc session:** judge against retrieved chunks (the student's own material), with a *more generous* concept-relevant retrieval than chat so "Complete" reflects what the document actually says.
- **Doc-less:** judge against general knowledge, scoped to *"the level appropriate for a student explaining this concept within the session's scope,"* not exhaustively — avoids grading against an LLM's entire knowledge.

**Anti-gaming (verbatim copy):** handled by the copied-verbatim archetype example (the scorer penalizes it). An optional deterministic code gate (explanation-vs-chunk similarity, doc sessions only) is **deferred** unless gaming is observed — copying mainly cheats the student.

**Injection:** structural, not the keyword blocklist — rubric/instructions in the system prompt; the explanation in a **delimited** user section the scorer is told never to obey; forced JSON output.

**Cost:** a Feynman evaluation is a generation call and **counts as 1 against the Daily Allowance** (ADR-0001); each retry counts again. BYOK lifts it.

**Retry:** a new attempt on the same concept; `attemptNumber` increments; every attempt is persisted. `retry_suggested` is **`true` when `overall_score < 70`** — a nudge, not a gate; the student can always retry or continue regardless.

## Consequences

- Scores are stable enough to track as a metric and to compare retries against.
- "Daily Allowance" now spans chat answers + Feynman evaluations — its unit is generalized from "messages" to "generation calls" (CONTEXT.md, ADR-0001, PRD updated).
- A heavy scoring prompt (rubric + ~5 exemplars + retrieved context) runs per evaluation — the lean exemplar count was chosen partly for this cost.
- Allowance-exhausted still needs a response shape shared with chat (open contract item).

## Considered alternatives

- **Fine 10-point bands / 10 exemplars:** more authoring + tokens, and finer bands reduce reliability. Rejected.
- **Gemini-emitted overall score:** drifts from the sub-scores. Rejected for the code-computed average.
- **Judge Correct/Complete always against general knowledge:** unfair to doc students, wastes the RAG pipeline. Rejected.
