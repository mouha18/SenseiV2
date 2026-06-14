# USER BLUEPRINT — Sensei

**Version:** 1.0
**Last Updated:** 2026-06-10
**Purpose:** Define every screen, user journey, edge case, and async event for the Sensei MVP.

---

## User Types

| User Type | Description | Entry Point |
|---|---|---|
| First-time student | Signs up, completes onboarding, starts first session | `/signup` |
| Returning student | Logs in, resumes or creates a new session | `/login` → `/dashboard` |

---

## Journey — First-Time Student

### Phase 1 — Discovery & Onboarding
**Goal:** Student creates an account and understands how Sensei works before starting.

| Step | Screen | What user does | What happens next | Notes |
|---|---|---|---|---|
| 1 | Landing (`/`) | Reads what Sensei is, clicks "Get Started" | Redirected to `/signup` | CTA prominent above fold |
| 2 | Signup (`/signup`) | Enters email + password, submits | Convex creates account, session token issued, redirected to `/dashboard` | |
| 3 | Dashboard (`/dashboard`) | Sees onboarding tour overlay | Tour highlights: New Session button, how scope works, what Feynman mode is | Tour shown once, dismissed on completion |
| 4 | Settings (`/settings`) | Enters Gemini API key, saves | Key stored encrypted in Convex, confirmation shown | Prompted to do this before first session if key missing |

### Phase 2 — Core Usage
**Goal:** Student has a full study session — uploads materials, asks questions, gets guided.

| Step | Screen | What user does | What happens next | Notes |
|---|---|---|---|---|
| 1 | Dashboard | Clicks "New Session" | New session created in Convex, redirected to `/session/[id]` | |
| 2 | Session | Optionally drops PDF(s) into UploadZone | Files sent to FastAPI `/ingest/upload`, processing status shown | Scope tag appears once ingestion complete |
| 3 | Session | Types first question (if no docs uploaded) | Question sent to `/chat/ask`, scope extracted and shown in ScopeTag | Scope locked from this point |
| 4 | Session | Continues asking questions | Socratic or direct answers displayed based on question type | |
| 5 | Session | Asks out-of-scope question | Gentle redirect message shown, out-of-scope count incremented | |
| 6 | Session | Clicks "Test Me" | FeynmanModal opens | |
| 7 | Session (modal) | Types concept name + submits explanation | POST `/evaluate/feynman` called, score shown in FeynmanResult | |
| 8 | Session (modal) | Clicks "Try Again" or "Continue" | Modal resets or closes | Score saved to Convex either way |

### Phase 3 — Retention & Return
**Goal:** Student comes back on their own to continue studying.

| Step | Screen | What user does | What happens next | Notes |
|---|---|---|---|---|
| 1 | Login (`/login`) | Enters credentials | Redirected to `/dashboard` | |
| 2 | Dashboard | Sees list of past sessions with scope and date | Clicks a session to reopen | Expired sessions shown as read-only |
| 3 | Session (past) | Reviews chat history and Feynman scores | No new messages can be sent if expired | |
| 4 | Dashboard | Clicks "New Session" to start a fresh one | New session created | |

---

## Journey — Returning Student

### Phase 1 — Re-entry
| Step | Screen | What user does | What happens next | Notes |
|---|---|---|---|---|
| 1 | Login (`/login`) | Enters credentials | Redirected to `/dashboard` | No onboarding tour |
| 2 | Dashboard | Reviews past sessions or starts new one | Continues as Phase 2 above | |

---

## Page Index

| Page | Route | Purpose | Used in Journey |
|---|---|---|---|
| Landing | `/` | Product intro, signup CTA | First-time Phase 1 |
| Signup | `/signup` | Create account | First-time Phase 1 |
| Login | `/login` | Authenticate | Returning Phase 1 |
| Dashboard | `/dashboard` | Session list, new session CTA | All users |
| Session | `/session/[id]` | Chat, upload, Feynman mode | All users Phase 2 |
| Settings | `/settings` | Gemini API key management | First-time Phase 1, any time |

---

## Edge Cases & Alternate Flows

| Scenario | Trigger | Where user lands | How it's handled |
|---|---|---|---|
| Missing Gemini API key on first message | User tries to chat with no key saved | Session page | Error message: "Please add your Gemini API key in Settings before chatting." Link to settings shown. |
| Invalid Gemini API key | Gemini returns auth error | Session page | Error message: "Your Gemini API key appears to be invalid. Please check it in Settings." |
| File too large (>5MB) | User drops a file over the limit | Session page | Upload rejected with message: "This file is too large. Maximum size is 5MB per file." |
| Session storage full (>20MB) | User tries to upload when session is at limit | Session page | Upload rejected: "Session storage limit reached (20MB). Start a new session to upload more." |
| 3 consecutive out-of-scope messages | User keeps asking off-topic questions | Session page | Message: "It looks like you want to explore a different topic. Would you like to start a new session on that subject?" with CTA button. |
| Session expired (3 days) | User opens a session older than 3 days inactive | Session page | Chat shown in read-only mode. Banner: "This session has expired. Start a new one to continue studying." |
| Gemini API slow/timeout | Gemini takes too long to respond | Session page | Loading indicator shown; after 30s timeout, error: "Sensei is taking too long to respond. Try again." |
| Ingestion fails | PDF is corrupted or unreadable | Session page | Error: "We couldn't process this file. Try a different PDF." |
| Rate limit hit (429) | User sends > 20 messages/minute | Session page | Message: "You're going fast! Wait a moment before sending another message." |
| Unauthenticated access | User navigates to `/dashboard` without logging in | Login page | Redirect to `/login` |

---

## Notifications & Async Events

| Event | Trigger | Channel | Deep link destination |
|---|---|---|---|
| Ingestion complete | FastAPI returns `{ status: "ready" }` | In-app (UI polling) | Session page — ScopeTag updates |
| Scope detected | Ingestion complete or first question processed | In-app toast | Session page |
| Feynman score saved | FeynmanResult displayed | In-app (no toast, inline) | FeynmanResult component |
| Session expiry warning | 3 days of inactivity approaching (future feature) | — | Not in MVP |
