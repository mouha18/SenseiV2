# SECURITY — Sensei

**Version:** 1.0
**Last Updated:** 2026-06-10

---

## 1. Threat Model

### Assets to Protect
- Student Gemini API keys (stored encrypted in Convex)
- Student uploaded documents (private course materials)
- Student chat history and Feynman scores (personal academic data)
- Supabase vector chunks (scoped per user — isolation critical)
- Gemini API quota (prevent abuse of student keys by other users)

### Threat Actors
- **Malicious student:** Attempts prompt injection or multi-turn conversational drift to bypass Socratic behavior. (Extracting other students' data is out of reach — cross-user data never enters a prompt; see ADR-0008.)
- **Automated scraper:** Hammers AI routes to exhaust rate limits or extract training data
- **Passive attacker:** Intercepts unencrypted traffic to steal API keys or chat content
- **Curious student:** Tries to access another student's session by guessing session IDs

### Key Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Prompt injection / role drift | Medium | Low | Cross-user isolation via scoping; role-locked system prompt; per-message scope gate; forced output schema (ADR-0008) |
| API key theft | Medium | High | Encrypted storage, never logged, never in responses |
| Cross-user data access | Low | High | RLS enforced via a restricted Postgres role + `SET LOCAL app.current_user_id` (not the service key — ADR-0009) + session ownership check in FastAPI |
| Rate limit abuse | Medium | Medium | Velocity limit (20/min, fixed window in Convex) + Daily Allowance on the Default Key (ADR-0001) |
| Session ID enumeration | Low | Medium | Convex auto-generates non-sequential IDs |
| Gemini key leakage via logs | Medium | High | Keys never logged — scrubbed before any log write |

---

## 2. Authentication & Authorization

- **Auth provider:** Convex Auth (email/password for MVP)
- **Token type:** Convex Auth JWT, managed by Convex
- **Token expiry:** Short-lived access token, auto-refreshed while active (bounds the revocation window — see below)
- **Inbound verification:** FastAPI verifies each JWT **offline** against Convex's published JWKS (signature, `exp`, `iss`, `aud`) and reads the user ID from the `sub` claim — no Convex round-trip, no shared secret. See [ADR-0003](./adr/0003-fastapi-convex-auth-boundary.md).
- **Revocation / logout:** each `users` row carries `tokensValidAfter`; FastAPI rejects any token issued before it. The check rides on the Convex call FastAPI already makes per request, so logout takes effect near-instantly with no extra round-trip.
- **Outbound (FastAPI → Convex):** FastAPI authenticates to a small set of purpose-built Convex HTTP endpoints with a shared service secret (`CONVEX_SERVICE_SECRET`) — least privilege, never the deploy key. See ADR-0003 and INTERNAL_API.md.
- **Inbound service calls (Convex → FastAPI):** the hourly expiry cron calls FastAPI's cleanup endpoint, which is **publicly reachable** (Convex cron runs on Convex's cloud, not a private network) and gated only by `CONVEX_SERVICE_SECRET` with a **constant-time** check (ADR-0006). The secret therefore lives in both environments; full wiring + the secrets matrix are in DEPLOYMENT.md.

**Roles (MVP):**
- `student` — the only role for MVP. All authenticated users are students.

**Key permission rules:**
- A user can only read/write their own sessions
- A user can only query chunks scoped to their own `user_id`
- A user's Gemini API key is only used for their own requests — never shared across users
- FastAPI never accepts a session_id without verifying the requesting user owns it

---

## 3. Data Security

- **Gemini API keys:** Encrypted at rest in Convex using AES-256 before storage. Decrypted in-memory only when needed for a Gemini call. Never returned in any API response. Never written to logs.
- **PII fields:** Email (Convex users table). No other PII collected for MVP.
- **Transit encryption:** All traffic over HTTPS/TLS. FastAPI deployed behind a TLS-terminating reverse proxy.
- **At-rest encryption:** Supabase encrypts data at rest by default. Convex encrypts data at rest by default.
- **Chat history:** Stored in Convex, accessible only to the owning user via Convex auth rules.

---

## 4. Secrets Management

- All secrets in `.env` files, never committed to git
- `.env` listed in `.gitignore` — enforced
- Production secrets stored in Railway/Fly.io environment variables (not in `.env` files on server)
- Supabase: FastAPI connects with a **restricted, RLS-subject Postgres role** for chunk access (enforced via `SET LOCAL app.current_user_id`), plus a **narrow Storage credential** for raw PDFs. The Postgres **service-role key is never placed in FastAPI** — it would bypass RLS (ADR-0009). Nothing Supabase-side is exposed to the frontend.
- Convex deploy key used only for deployments/admin — never in the request path
- `CONVEX_SERVICE_SECRET` — shared secret for FastAPI → Convex server-to-server calls, scoped to purpose-built endpoints (least privilege — see ADR-0003)
- Gemini key-encryption secret — held only by FastAPI, used to encrypt/decrypt BYOK keys (ADR-0002)
- Rotation policy: rotate all keys immediately if any are suspected compromised

---

## 5. API Security

**Input validation:**
Every FastAPI route uses Pydantic models for automatic type and shape validation. Malformed requests are rejected with 422 before any business logic runs.

**Prompt injection & role integrity (see ADR-0008):**
No keyword blocklist — it is bypassable by rephrasing and produces false positives on legitimate study text (e.g. "act as a catalyst"), and the realistic threat is multi-turn drift, not single-shot injection. Role integrity is defended in layers instead:

- **Architectural isolation:** secrets and other users' data never enter any prompt (RLS + user/session scoping; the Gemini key lives only in FastAPI), so an injection has nothing cross-user to leak.
- **Role-locked system prompt:** defines Sensei's role and a boundaried disposition; the student message and retrieved chunks sit in delimited sections treated as content, never instructions; Sensei refuses persona/role/format changes and does not cave to insistence, flattery, or frustration. For out-of-role needs (medical/legal/personal-safety) it briefly signposts appropriate help and steers back, without adopting that role.
- **Instruction sandwiching:** the role instruction is restated after the user content so long/adversarial inputs don't drag it off.
- **Scope gate (ADR-0004):** the per-message scope check redirects off-role tangents before generation, every turn — closing the multi-turn-drift off-ramp.
- **Forced output schema:** derailed or non-conforming output is rejected in code.
- **Gemini safety filters:** for genuinely harmful generation on the Default Key.

**Rate limiting & cost control (two distinct controls — never conflate them):**
- **Velocity limit** — 20 requests/minute/user, anti-abuse, applies to everyone including BYOK. A **fixed window on the Convex `users` row** (not in-process middleware — survives deploys and horizontal scaling), consumed in the per-request service call (ADR-0001). Over limit → `429 RATE_LIMITED`.
- **Daily Allowance** — 20 Default-Key generation calls/day/user, cost cap, lifted under BYOK; counts delivered answers, not attempts (failed/blocked calls refunded — ADR-0001). Exhausted → `429 ALLOWANCE_EXHAUSTED`.

**CORS:**
Configured on FastAPI to allow only the frontend origin. All other origins rejected.

**Gemini key never transmitted by the client:**
Per ADR-0002, the client never sends a Gemini key. FastAPI fetches the encrypted blob from Convex by verified user ID and decrypts it in-memory for the call; the Default Key lives only in the FastAPI environment. Keys never appear in request bodies, URLs, query parameters, or logs.

---

## 6. Dependency Security

- `pip audit` run before every deployment to check for known CVEs in Python dependencies
- `npm audit` run before every frontend deployment
- Dependabot enabled on GitHub repo for automated dependency update PRs
- No dependency pinned to a known vulnerable version — all pinned to latest stable at time of writing
- CVE policy: any critical CVE in a direct dependency is patched within 48 hours

---

## 7. Incident Response

1. **Detect** — Error monitoring (Sentry) alerts on 5xx spike or anomalous Gemini usage
2. **Contain** — Disable affected route or user account immediately via Convex admin
3. **Assess** — Review logs to determine scope of breach (what data, which users, how long)
4. **Notify** — If user data is confirmed compromised, notify affected users by email within 72 hours
5. **Fix** — Patch the vulnerability, rotate any exposed secrets, redeploy
6. **Post-mortem** — Document root cause, impact, fix, and prevention measures within 1 week
