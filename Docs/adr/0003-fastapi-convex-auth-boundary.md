# 0003 — FastAPI ↔ Convex auth boundary

**Status:** Accepted

## Context

FastAPI (Python) and Convex (JavaScript) are separate services, and the browser calls FastAPI directly. Two distinct trust problems result:

1. **Inbound** — FastAPI must trust *which student* is calling, so it can enforce the Daily Allowance, fetch the right key, and scope data access.
2. **Outbound** — FastAPI must authenticate *itself* when it calls Convex (to check/increment the allowance per ADR-0001, fetch the encrypted key per ADR-0002, and read logout state).

The original docs conflated these and described mechanisms that don't fit the stack: "verify every token via the Convex server SDK" (the server SDK is JS — there is no Python equivalent) and "Convex deploy key used for token verification" (the deploy key is deployment-wide *admin* credentials, not a token verifier, and far too privileged to sit in the request path).

## Decision

**Inbound — trusting the student (no secret, no round-trip):**

- Convex Auth issues JWTs and publishes a JWKS (public keys). FastAPI verifies each bearer token **offline** with a standard library (signature, `exp`, `iss`, `aud`) and reads the Convex user ID from the `sub` claim.
- **Revocation / logout:** each `users` row carries `tokensValidAfter` (timestamp). FastAPI rejects any token whose issued-at (`iat`) precedes it. The check rides on the Convex call FastAPI *already* makes each request (allowance + key fetch), so logout takes effect near-instantly with **no extra round-trip**. Access tokens are kept short-lived (auto-refreshed while active) to bound the window further.

**Outbound — FastAPI proving itself to Convex (least privilege):**

- FastAPI does **not** hold the Convex deploy key. Convex exposes a small set of purpose-built HTTP endpoints (consume allowance, fetch key material + `tokensValidAfter` + session owner) guarded by a shared secret `CONVEX_SERVICE_SECRET` sent in a header.
- A FastAPI compromise can therefore invoke only those specific operations — not arbitrary admin, not bulk data export, not code deploys.

## Consequences

- Inbound verification adds zero latency and needs no secret (public keys only).
- A breach of FastAPI — the most externally exposed service (uploads, PDF parsing, Gemini calls) — cannot read/wipe all Convex data or deploy code; blast radius is the few exposed service endpoints.
- FastAPI's environment now holds two critical secrets: the key-encryption secret (ADR-0002) and `CONVEX_SERVICE_SECRET`. Both follow the rotation policy.
- The Convex deploy key reverts to its proper role: deployments/admin only, never in the request path.
- **To confirm against Convex Auth docs (not verified live here):** the exact JWKS URL, issuer/audience values, and `sub` claim shape.

## Considered alternatives

- **Verify via the Convex JS server SDK:** unavailable in Python. Rejected.
- **Per-request callback to Convex to validate the token:** authoritative and supports instant revocation, but adds a round-trip to *every* AI call and requires a custom endpoint. Offline JWT + `tokensValidAfter` gives near-equivalent revocation without the latency. Rejected.
- **Deploy key for outbound calls:** simplest, but grants full admin to the most-exposed service — a FastAPI breach would mean total Convex compromise. Rejected for least privilege.
