# 0008 — Prompt injection & role integrity: drop the blocklist, defend in layers

**Status:** Accepted

## Context

The original defense was a keyword blocklist (`INJECTION_PATTERNS`) returning `400 INJECTION_DETECTED`, plus system-prompt anchoring. The blocklist is bypassable by trivial rephrasing **and** produces false positives on legitimate study text ("act as a catalyst", quoting "you are now…"). More importantly, the threats it nominally guards are mostly moot here:

- **Extracting other students' data is impossible by construction.** RAG is scoped by `user_id` + `session_id` (RLS + app scoping), so a prompt only ever contains *this* student's chunks and conversation; the Gemini key lives in FastAPI, never in a prompt. Isolation is **architectural**, not prompt-based.
- **Bypassing the Socratic method is self-inflicted** and low-stakes.

The realistic threat is **not single-shot injection but multi-turn conversational drift**: a model's helpfulness/empathy is used to walk it off its role over several turns (the documented real-world failure — e.g. a career-service bot that resisted "ignore your instructions" but, fed emotional distress, offered an off-ramp and then answered anything). A single-message blocklist cannot address that.

## Decision

- **Drop the keyword blocklist and the `INJECTION_DETECTED` rejection entirely** (no telemetry).
- Defend role integrity in layers:
  1. **Architectural isolation** — no secrets or other-user data in any prompt.
  2. **Role-locked, boundaried system prompt** — refuses persona/role/format changes; does not cave to insistence, flattery, or frustration; treats the student message and retrieved chunks as delimited content, never instructions; for out-of-role needs (medical/legal/personal-safety) it briefly signposts appropriate help and steers back, **without adopting that role**.
  3. **Instruction sandwiching** — the role is restated after the user content.
  4. **Per-message scope gate (ADR-0004)** — redirects off-role/off-topic tangents *before* generation, every turn; closes the multi-turn-drift off-ramp.
  5. **Forced output schema** — derailed output is rejected in code.
  6. **Gemini safety filters** — for genuinely harmful generation.

## Consequences

- No false rejection of legitimate study questions; the `INJECTION_DETECTED` path is removed (SECURITY, ARCHITECTURE, API design, roadmaps).
- **Indirect injection via uploaded PDFs** (malicious text inside a chunk) is covered by the same delimiting — something the blocklist never addressed.
- Role integrity rests on structural + deterministic guards, not keyword matching — materially harder to break than a single-line role prompt, though not absolutely jailbreak-proof; the residual failure (one off-character reply in the student's *own* session) is contained and low-stakes.
- The planned `sensei-api/utils/injection.py` component is no longer built.

## Considered alternatives

- **Keep/expand the blocklist:** unbounded rephrasings + false positives, and it never addresses multi-turn drift. Rejected.
- **LLM-based injection classifier per message:** extra call, cost, and latency, still probabilistic; the scope gate + role-lock cover the realistic threat more cheaply. Rejected for MVP.
