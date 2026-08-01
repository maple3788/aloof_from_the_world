# Project Progress — Aloof from the World

Session handoff log. Newest session first. For a quick review: read the snapshot,
the latest session entry, and "Next steps".

## Current state snapshot

- Multi-agent RAG chat: FastAPI + LangGraph + Chroma/SQLite backend, Next.js 16 SSE frontend.
- **36 backend + 8 frontend tests passing** (`make test` = pytest + eslint + vitest);
  ruff lint clean; frontend `tsc --noEmit` + eslint clean.
- SQLite is a **single shared connection** on `app.state.db` (WAL mode, `asyncio.Lock`),
  opened/closed in the FastAPI lifespan.
- Frontend aborts in-flight streams/session fetches on session switch, new chat, unmount.
- CI: GitHub Actions (`.github/workflows/ci.yml`) — backend pytest, frontend eslint +
  vitest + `next build`.
- Optional **Redis cache layer** for retrieval results + critic verdicts — off by default,
  enabled via `REDIS_URL` (see `backend/.env.example`); wired automatically in `make docker`.
- `store.retrieve()` is **async** (cache support); callers in `retriever.py`, `personas.py`,
  `tutor.py` await it.

## Session log

### 2026-08-01 — M1–M3: shared SQLite connection, frontend aborts + tests, CI

- **M1** `db.py` rewritten as a `Database` class: one shared aiosqlite connection on
  `app.state.db`, every method behind an `asyncio.Lock` (multi-statement writes stay
  atomic), `PRAGMA journal_mode=WAL` at connect; lifespan closes it on shutdown.
  Routers read `request.app.state.db`. New test `test_database_uses_wal_mode`.
- **M2** `page.tsx` holds `AbortController`s for the SSE stream and the session-detail
  fetch; both abort on session switch / new chat / unmount — stream tokens no longer
  bleed into a newly selected session; `AbortError` is swallowed silently.
  `api.getSession` accepts a signal. First component tests: Vitest + Testing Library
  (jsdom) — `Composer.test.tsx` + `PersonaPicker.test.tsx` (8 tests);
  `npm run lint` + `npm test` wired into `make test`.
- **M3** `.github/workflows/ci.yml`: backend job (uv sync + pytest), frontend job
  (npm ci + eslint + vitest + `next build`); Node 22, uv/npm caches on.
- Verification: `make test` (36 backend + 8 frontend), ruff, tsc, eslint, `next build`
  all clean.


### 2026-07-31 — Architecture review, Redis cache, robustness fixes

- Ran a full architecture review (architect subagent) — verdict: well-architected for its
  size; main risks were unbounded LLM history, serialized critic latency, mid-stream
  persistence gap, no input limits. Full findings: canvas artifact at
  `~/.cursor/projects/Users-mapleandrew-AIproject-aloof-from-the-world/canvases/architecture-review.canvas.tsx`
- **Decision**: Redis adopted as a *cache layer only* (user's call) — not a vector store,
  not a primary DB. Chroma + SQLite remain the data stores.
- Implemented quick wins W1–W7:
  - `backend/app/cache.py`: RedisCache/NullCache behind one interface, content-hash keys,
    TTLs (`CACHE_TTL_RETRIEVAL=3600`, `CACHE_TTL_CRITIC=86400`); `make ingest` flushes the
    `rag` namespace.
  - W1 root `.dockerignore` (also keeps `**/.env` out of images).
  - W2 `MAX_HISTORY_MESSAGES=20` — only the recent tail goes to the LLM; full history in SQLite.
  - W3 `max_length=4000` on `ChatRequest.message` (422 beyond).
  - W4 critic reviews run via `asyncio.gather` (was serial).
  - W5 stream errors persist accumulated partial replies — no more orphaned user messages.
  - W6 Chroma private APIs isolated into `store.py` helpers (`delete_work_chunks`,
    `count_work_chunks`, `count_all_chunks`, `drop_collection`).
  - W7 README `color: sky` → `amber`; `/health` exposes `max_personas` + `cache` status;
    frontend reads the cap from `/health` instead of hardcoding.
- Infra: `redis:7-alpine` service in docker-compose; `.env.example` + README updated.
- Verification: 35 tests (was 24), ruff, tsc, eslint, `docker compose config` all clean.
- Known quirk: repo is not `ruff format`-clean (pre-existing drift in ~10 untouched files);
  lint passes. Deliberately not reformatted (surgical-changes rule).

## Next steps

From the review, not yet scheduled (M1–M3 done 2026-08-01):

- **M4** History summarization node — only if W2 truncation proves lossy in practice.
- **M5** Pre-deployment gate (only before any non-localhost exposure): shared-token auth,
  rate limiting, sanitized error payloads, env-driven CORS.
- **L3/L4** Persona YAML: validate at startup with friendly errors; document that adding a
  card requires a server restart (`load_personas` is `lru_cache`d).

## Pointers

- Config/env reference: `backend/.env.example`
- Architecture review canvas: see session log above
- Agent definitions: `.cursor/agents/` (architect is read-only; use for design reviews)
