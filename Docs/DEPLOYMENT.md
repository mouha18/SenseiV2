# DEPLOYMENT — Sensei

**Audience:** whoever deploys and operates Sensei. This is the *how/where* — which platform holds which secret, how the two backends reach each other, and what to rotate. The *why* lives in SECURITY and the ADRs; the *what* lives in ARCHITECTURE.

---

## 1. Topology

| Component | Hosted on | Notes |
|---|---|---|
| Frontend (Next.js) | Vercel | Static + edge; talks to Convex (data) and FastAPI (AI) |
| FastAPI AI backend | Railway / Fly.io | Behind the platform's TLS proxy; single instance for MVP (ARCHITECTURE §6) |
| Convex | Convex Cloud (managed) | Auth, metadata, chat history, cron |
| Supabase | Supabase Cloud (managed) | Postgres + pgvector (`chunks`) and Storage (raw PDFs) |

CORS on FastAPI is locked to the Vercel frontend origin(s). No route is open `*`.

---

## 2. The Convex ↔ FastAPI wiring (read this before deploying)

Traffic crosses the public internet in **both** directions. Neither service is on the other's private network.

**FastAPI → Convex** (per request — ADR-0001, ADR-0002, ADR-0003)
FastAPI calls Convex's purpose-built HTTP endpoints (consume allowance, fetch encrypted key + `tokensValidAfter` + session owner) on the **`.convex.site`** host, authenticating with `CONVEX_SERVICE_SECRET` in a header.

**Convex → FastAPI** (hourly cron — ADR-0006)
Convex cron calls FastAPI's cleanup route to delete an expired session's chunks + PDFs.

> ⚠️ **The cleanup route is "internal" by purpose, not by network.** Convex cron runs on Convex's cloud, so it reaches FastAPI over the **public internet**. The route must be **publicly reachable** (behind the TLS proxy), gated *only* by `CONVEX_SERVICE_SECRET`. If you firewall it to a private network, expiry silently never runs — Supabase fills up with no error anywhere. A leaked secret lets a caller force-expire **any** session by id (targeted data destruction), so: constant-time secret compare, and the route stays idempotent (replays are no-ops). See ADR-0006.

**Token verification** (inbound, no round-trip — ADR-0003)
FastAPI verifies Convex Auth JWTs **offline** against the published JWKS. Convex Auth exposes `/.well-known/jwks.json` and `/.well-known/openid-configuration` on the **`.convex.site`** host once the app calls `auth.addHttpRoutes()`. Tokens are RS256-signed.
- **Issuer (`iss`):** the `.convex.site` URL.
- **Audience (`aud`):** `convex` (Convex Auth default).
- **JWKS URL:** `<CONVEX_SITE_URL>/.well-known/jwks.json`.

---

## 3. Secrets matrix

| Secret | Lives in | Purpose / ADR |
|---|---|---|
| `GEMINI_API_KEY` (Default Key) | FastAPI env | Default-Key generation calls — ADR-0001 |
| `KEY_ENCRYPTION_SECRET` | FastAPI env | Encrypt/decrypt stored BYOK keys — ADR-0002. **Rotating = re-encrypt every stored blob.** |
| `CONVEX_SERVICE_SECRET` | **FastAPI env + Convex env** | Both directions: FastAPI→Convex service calls (ADR-0003) and Convex cron→cleanup (ADR-0006). **Rotation touches both stores at once.** |
| `CONVEX_SITE_URL` (+ derived JWKS URL / `iss` / `aud`) | FastAPI env | Offline token verification + service-endpoint base — ADR-0003. Use the **`.convex.site`** host, **not** `.convex.cloud`. |
| FastAPI production URL | Convex env | So cron can call cleanup — ADR-0006 |
| Supabase **restricted-role DSN** | FastAPI env | All `chunks` work, RLS-enforced via `SET LOCAL app.current_user_id` — ADR-0009. A non-superuser role, **not** the service key. |
| Supabase **Storage credential** | FastAPI env | Raw-PDF upload + delete-on-expiry — ADR-0009. Narrow Storage scope, not the DB service key. |

**Never** placed in FastAPI's env: the Convex **deploy key** (ADR-0003) and the Supabase **service-role key** (ADR-0009). Both over-grant the most-exposed service. Nothing secret is ever client-side.

---

## 4. Rotation runbook

- **`CONVEX_SERVICE_SECRET`** — update in **both** Convex env and FastAPI env. Brief overlap window: deploy the new secret to the verifier (FastAPI) first, then the caller (Convex), to avoid a gap where cron calls are rejected.
- **`KEY_ENCRYPTION_SECRET`** — cannot be rotated in place: re-encrypt all stored BYOK blobs under the new secret (or force users to re-enter keys). Plan a migration; don't rotate casually (ADR-0002).
- **`GEMINI_API_KEY`** — swap in FastAPI env; affects only Default-Key users.
- **Supabase restricted-role DSN / Storage credential** — rotate independently of each other; restricted role first if both change.

---

## 5. Pre-launch reachability checklist

- [ ] FastAPI cleanup route is reachable from the public internet (curl it with the service secret → 200; without → 401/403).
- [ ] Convex env has the correct FastAPI prod URL (trailing slash / scheme correct).
- [ ] FastAPI env points at the `.convex.site` host for JWKS + service endpoints (not `.convex.cloud`).
- [ ] CORS allows only the Vercel origin(s).
- [ ] FastAPI connects to Supabase as the **restricted role**, and a smoke query without `SET LOCAL` returns **no** rows (proves RLS is live, not bypassed).
- [ ] Hourly Convex cron registered; trigger one manual run and confirm an expired session's chunks + PDFs are gone and `status:"expired"` is set.
