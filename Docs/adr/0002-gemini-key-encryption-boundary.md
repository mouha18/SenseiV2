# 0002 — Gemini key encryption boundary: FastAPI holds the secret, Convex stores only ciphertext

**Status:** Accepted

## Context

BYOK keys must be persisted (PRD F5) and used by FastAPI to call Gemini. If a stored key can be decrypted by whoever holds the database, a single breach of that store harvests every student's Gemini key. We want a stored BYOK key to survive the compromise of any *one* system. Encryption only delivers that when the ciphertext and the decryption secret live in **different trust domains** — if one system holds both, the encryption adds little over the access control already in place. See [ADR-0001](./0001-default-key-daily-allowance-byok.md) for the surrounding key model.

## Decision

- **FastAPI is the sole holder of the encryption secret** (symmetric, in its environment). It performs **both** encryption (at save) and decryption (at use).
- **Convex stores only the opaque ciphertext** in `users.geminiApiKey`. It never holds the secret and never sees plaintext.
- **Save flow:** frontend sends plaintext to FastAPI → FastAPI validates it with a test Gemini call (F5) → encrypts → returns the blob → frontend writes the blob to Convex.
- **Use flow:** per request, FastAPI fetches the blob from Convex by the **verified** `userId` — the same server-to-server call it already makes for the Daily Allowance check (ADR-0001) — decrypts in memory, uses it, discards. Blob present → BYOK; absent → Default Key.
- Plaintext therefore exists only fleetingly: in the browser at the moment of entry, and inside FastAPI per request. Convex and the browser-after-setup only ever handle ciphertext.

## Consequences

- A Convex breach yields only ciphertext — useless without FastAPI's secret. Harvesting a stored key requires breaching **both** systems.
- FastAPI's encryption secret is now critical. Rotating it requires re-encrypting all stored blobs (or forcing users to re-enter keys). Acceptable for MVP; flagged for ops.
- FastAPI must verify the Convex token to trust `userId` before fetching/decrypting. That verification is a separate decision (the auth/token model), not settled here.
- Symmetric (not asymmetric) because the same party — FastAPI — both encrypts and decrypts; asymmetric would add key-management overhead with no benefit.

## Considered alternatives

- **Secret + ciphertext both in Convex** (secret in a Convex env var, a Convex action decrypts): a single Convex/env compromise harvests every key; encryption barely exceeds the existing access control. Rejected.
- **Client-side encryption with a user passphrase:** strongest (neither Convex nor FastAPI sees plaintext), but forces a passphrase prompt every session and a lost passphrase loses the key. Rejected for MVP UX.
- **Frontend forwards the blob per request:** lets a malicious client choose which blob to submit. Rejected for the trust hole; FastAPI fetching by verified `userId` closes it.
