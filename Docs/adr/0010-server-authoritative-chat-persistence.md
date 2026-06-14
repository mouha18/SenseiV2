# 0010 — Server-authoritative chat persistence: FastAPI reads and writes history

**Status:** Accepted

## Context

The original chat flow (ARCHITECTURE data flow #2) made the **client** the authoritative writer of chat history: the browser read the last N messages from Convex, replayed them to FastAPI as `conversation_history`, and — after receiving the answer — wrote both the user message and the assistant message back to Convex. FastAPI stayed out of the Convex write path.

That put the client in the authority path and created three correctness problems in the **core** chat loop, not just edge polish:

1. **Dangling turns corrupt future requests.** A crash/navigation/network drop between receiving the answer and writing to Convex leaves a user message with no reply (or nothing). The next `/chat/ask` then replays a `conversation_history` that doesn't match reality — and that history drives both the answer and the Socratic one-round cap (ADR-0004).
2. **Allowance ↔ history desync.** The allowance is incremented server-side at the Gemini call (ADR-0001); the message is persisted client-side afterward. Two actors, no atomicity — a student can be charged a generation call that produced no stored message, making history unauditable.
3. **`lastActivityAt` ambiguity.** If the client owns the message write, a real answered turn the client fails to persist also fails to bump activity (ADR-0006), so a session can expire despite genuine use.

Plus a standing trust caveat: client-supplied `responseType` in the replayed history is spoofable (ADR-0004 accepted this as low-stakes) — same root cause, the client is in the authority path.

## Decision

**FastAPI is the authoritative reader *and* writer of chat history.** It uses the same narrow, secret-gated Convex service channel it already uses for allowance/key (ADR-0003) — so FastAPI doesn't become stateful; it becomes the authoritative writer of AI-produced records, while Convex still owns storage + real-time sync.

Per `/chat/ask`:
- **Start (one Convex mutation):** consume-allowance check-and-increment (ADR-0001) *and* return the request context — encrypted key + `tokensValidAfter` + session owner/status + the **last N messages**. FastAPI no longer trusts a client-supplied transcript.
- **Gemini call** with the assembled prompt (system + server-read history + context + question).
- **End (one Convex mutation):** persist the **user message + assistant message** (with the server-computed `responseType`/`source`) and **bump `lastActivityAt`**, atomically.

**`conversation_history` is dropped from the `/chat/ask` request body.** Out-of-scope and redirect turns are persisted by FastAPI too, with the authoritative `responseType` it computed.

The frontend renders from the Convex subscription (optionally optimistic, reconciled by the subscription) — it no longer reads-then-replays history, and no longer writes messages for the chat route.

**The same rule extends to Feynman.** A Feynman evaluation is also a charged generation call (ADR-0007), so the invariant applies identically: **FastAPI — not the client — persists the score**, atomically, refunding the allowance on a failed eval (ADR-0001). The roadmap's client-side `saveFeynmanScore` is replaced by a `persistFeynman` service endpoint; the client renders the result from the Convex subscription. Leaving Feynman client-written would reintroduce the dangling-record / allowance-desync problem this ADR removes for chat, just in another feature. The full internal surface is specified in `INTERNAL_API.md`.

## Consequences

- **New invariant:** every generation call yields exactly one persisted assistant message and one allowance decrement, written by the same party. History becomes auditable and matches the allowance.
- The client gets **simpler**: no transcript replay, no message write for chat.
- `responseType` is now **server-owned** end-to-end, removing the spoofable-replay caveat and retroactively strengthening ADR-0004 (the Socratic-cap signal) and ADR-0008 (role integrity).
- **Two Convex round-trips per chat** on FastAPI's side (consume+context, then persist) instead of one — inherent, since the charge must precede Gemini and the reply can't be stored until after it. Marginal at MVP scale; replaces two *client*→Convex calls.
- Two new Convex service endpoints (read-recent-messages, persist-turn) widen what a leaked `CONVEX_SERVICE_SECRET` can do to *writing messages into a session* — same category as the allowance/key access it already grants, not a new class of breach.
- **The failed-Gemini case now has a clear home:** the persist mutation is where a refund/no-store decision for a Gemini error lands (open item, tracked separately from this ADR).
- Forces edits: API_CONTRACT (`/chat/ask` request drops `conversation_history`) and ARCHITECTURE data flow #2 (FastAPI reads history + writes the turn; frontend renders from subscription).

## Considered alternatives

- **Client-writes (status quo):** simplest and idiomatic Convex, but accepts dangling turns, allowance/history desync, and spoofable replay in the core loop. Rejected — these are correctness issues, not polish.
- **Hybrid (client writes the user message, FastAPI writes the assistant message):** splits authority across two actors and can still desync / dangle. Rejected.
- **FastAPI writes but still trusts client-supplied `conversation_history`:** keeps the spoof and the replay-drift risk even though FastAPI just wrote the canonical rows. Rejected — if FastAPI is the writer, it should be the reader.
