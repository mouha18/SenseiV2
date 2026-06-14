# CONTRIBUTING — Sensei

---

## Branch Strategy

```text
main          → production-ready code only, deploys automatically to Vercel + Railway
dev           → integration branch, all features merge here first
feat/*        → one branch per feature (e.g. feat/rag-pipeline, feat/feynman-modal)
fix/*         → bug fixes (e.g. fix/scope-detection-edge-case)
chore/*       → non-feature work (e.g. chore/update-dependencies)
```

Never commit directly to `main`. All changes go through a `feat/*` or `fix/*` branch → `dev` → `main`.

---

## Commit Convention

```text
feat: add Feynman evaluation route
fix: correct chunk overlap calculation in embedder
chore: update pydantic to 2.7.0
docs: add API contract for evaluate endpoint
refactor: extract scope logic into utils/scope.py
test: add unit test for scope threshold gate
```

Format: `type: short description in lowercase, present tense`
Max 72 characters in the subject line.

---

## Development Workflow

1. Pull latest `dev` — `git pull origin dev`
2. Create a branch — `git checkout -b feat/your-feature-name`
3. Write code, commit frequently with conventional commits
4. Before pushing: run linting and type checks
   - Frontend: `npm run lint && npm run typecheck`
   - FastAPI: `ruff check . && mypy .`
5. Push branch — `git push origin feat/your-feature-name`
6. Open PR against `dev`, not `main`
7. Self-review the diff before marking ready
8. Merge to `dev` once satisfied
9. Merge `dev` → `main` only when a full feature set is tested end-to-end

---

## Code Standards

- **TypeScript strict mode** enabled — no implicit `any`, no type assertions without justification
- **No secrets in code** — all keys and URLs via environment variables only
- **Thin routers** — FastAPI route handlers must not contain business logic; delegate to services
- **Pydantic for all inputs** — every FastAPI route must use a Pydantic model for request validation
- **Async/await for all external calls** — Gemini, Supabase, embedding model — always async
- **No raw string concatenation for prompts** — always use structured system + user sections
- **RLS enforced** — every Supabase query must be scoped to `user_id`; never query without a user filter
- **No console.log in production** — use proper logging (Python `logging` module, not `print`)
- **Convex mutations for all writes** — never write to Convex from FastAPI directly; frontend owns Convex writes

---

## Questions

Open a GitHub Discussion or drop a message in the project chat. Don't guess — ask.
