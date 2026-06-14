# 0001 — Default Key with Daily Allowance, BYOK to lift the cap

**Status:** Accepted

## Context

Sensei calls Google Gemini for every chat answer, every RAG query embedding, and every Feynman score. Gemini is paid per call. We want a new student to be able to use the product immediately — without pasting an API key first — while keeping the platform owner safe from unbounded cost and abuse on a publicly shareable URL.

The original PRD (F5) specified pure BYOK: every call uses the student's own key, "never a platform key," "no API cost to the platform." That guarantees zero platform cost but blocks a brand-new user from sending a single message until they obtain and paste a Gemini key — heavy onboarding friction for a study tool.

## Decision

A hybrid key model:

- **Default Key** — the platform owner's single Gemini key, held in the FastAPI environment, used for any student who has not supplied their own.
- **Daily Allowance** — a student on the Default Key may make 20 Gemini generation calls per day (chat answers + Feynman evaluations). The counter lives on the Convex `users` row (`dailyDefaultKeyCount` + `dailyCountResetAt`) and resets at UTC midnight. Check-and-increment runs inside a single transactional Convex mutation, so the counter is race-free. FastAPI increments it only for Default-Key calls.
- **Refund on no usable answer** — the increment happens *before* the Gemini call (so concurrent bursts can't slip past the check), but if the call yields no usable answer to the student, the counter is **decremented back** in the same end-of-request mutation FastAPI already runs (ADR-0010). "No usable answer" covers transport errors, 5xx, timeouts, **safety-filter blocks**, and unrecoverable schema-invalid output. A genuine answer the student merely dislikes is **not** refunded. The allowance therefore counts *delivered answers*, not *attempts*. Applies identically to chat answers and Feynman evaluations (ADR-0007).
- **BYOK** — a student who saves their own Gemini key (stored encrypted in Convex, forwarded per request to FastAPI) has the Daily Allowance lifted; their usage is billed to them.
- **Velocity rate limit** — 20 requests/minute/user, anti-abuse, applies to everyone including BYOK, independent of the allowance. It lives in **Convex**, not FastAPI memory — folded into the per-request start mutation FastAPI already makes (ADR-0010), so it costs **no extra round-trip or function call**, and unlike an in-memory bucket it survives deploys and stays correct under horizontal scaling. A fixed window on the `users` row (`velocityCount` + `velocityWindowStart`): if `now − velocityWindowStart ≥ 60s`, open a new window (`velocityWindowStart = now`, `velocityCount = 1`); otherwise reject when `velocityCount ≥ 20`, else increment `velocityCount`. **The anchor is not restamped on in-window requests** — doing so would slide the window forward indefinitely and degrade the limit into a 20-*total* cap. Boundary bursts (up to ~40 across a window edge) are acceptable for anti-abuse; a token bucket smooths them if ever needed.
- **Ordering — velocity and allowance are separate Convex touches.** Velocity is checked at the **start** of every request, before any embedding (cheap early rejection). The allowance is a **separate, later** mutation, run only after the in-scope decision (ADR-0004) and only for Default-Key calls — so out-of-scope messages consume velocity but **not** the allowance. Both are individually atomic in Convex (the race-safety point); they simply fire at different moments because the scope check sits between them.

When a Default-Key student exhausts the allowance, they are prompted to add their own key rather than blocked outright.

## Consequences

- FastAPI must call Convex server-to-server to check/increment the allowance before any Default-Key Gemini call. A deliberate, narrow coupling; otherwise FastAPI stays stateless.
- The platform owner carries **bounded** Gemini cost — at most ~20 messages/day per registered user on the Default Key. This is not zero, contrary to the original "no API cost" framing.
- The cap counts *delivered* answers, so it is slightly looser than "20 billed calls/day": a refunded safety-block was still billed to the platform. Accepted — such failures are rare, and the fairness of never charging a student for a non-answer outweighs the marginal cost leak.
- Two distinct controls now exist and must never be conflated: the **Daily Allowance** (cost cap; daily; Default Key only) and the **velocity rate limit** (anti-abuse; per-minute; everyone).

## Considered alternatives

- **Pure BYOK** (original PRD F5): zero platform cost, but a new user cannot use the product at all before pasting a key. Rejected for onboarding friction.
- **Always-on Default Key, no allowance:** simplest UX, but unbounded cost/abuse on a public URL. Rejected.
- **Enforce the counter in FastAPI memory:** resets on deploy and breaks under the horizontal scaling ARCHITECTURE.md anticipates. Rejected in favour of Convex.
