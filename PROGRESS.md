# Project Progress — Aloof from the World

Session handoff log. Newest session first. For a quick review: read the snapshot,
the latest session entry, and "Next steps".

## Current state snapshot

- Multi-agent RAG chat: FastAPI + LangGraph + Chroma/SQLite backend, Next.js 16 SSE frontend.
- **129 backend + 34 frontend tests passing** (`make test` = pytest + eslint + vitest);
  ruff lint clean; frontend `tsc --noEmit` + eslint clean; `next build` green.
- Any **OpenAI-compatible API** works via `OPENAI_BASE_URL` (DeepSeek verified — see
  `backend/.env.example`); user runs hosted DeepSeek as the daily driver.
- SQLite is a **single shared connection** on `app.state.db` (WAL mode, `asyncio.Lock`),
  opened/closed in the FastAPI lifespan.
- Frontend aborts in-flight streams/session fetches on session switch, new chat, unmount.
- CI: GitHub Actions (`.github/workflows/ci.yml`) — backend pytest, frontend eslint +
  vitest + `next build`.
- Optional **Redis cache layer** for retrieval results + critic verdicts — off by default,
  enabled via `REDIS_URL` (see `backend/.env.example`); wired automatically in `make docker`.
- `store.retrieve()` is **async** (cache support); callers in `retriever.py`, `personas.py`,
  `tutor.py` await it.
- **Per-session language** (English default / 中文): `sessions.language` column (auto-migrated),
  `POST /sessions` accepts `language`; agents reply in it; zh queries are translated to
  English for retrieval (`app/agents/i18n.py`); persona cards carry `greeting_zh`; chat UI
  chrome is localized via `frontend/src/lib/i18n.ts`.
- **Trace board** (`/traces`): every user query persists a trace (router decision, zh
  translation, per-persona retrieval docs + latencies, reply latencies, critic verdicts,
  status ok/error/aborted). `TraceRecorder` rides the graph `trace` state channel
  (`NullRecorder` default); `chat.py` saves after the stream; `GET /traces` +
  `GET /traces/{id}`; traces cascade with their session.
- **Reading room** (`/read/{workId}`): full work text beside a chat panel (docks left or
  right) with the work-author's persona; highlight a passage → "Ask about selection".
  `GET /library/works/{id}/text` serves the cached Gutenberg text; reading sessions carry
  `sessions.work_id` (titled "Reading …", retrieval scoped to the work via `$and` filter).
- **Persona forge** (`app/agents/persona_forge.py`): works whose author has no card get one
  generated on demand — Wikipedia summary (best-effort) → LLM drafts card JSON (few-shot
  exemplar, pydantic-validated, one repair retry) → YAML written to `app/personas/` →
  `load_personas.cache_clear()` makes it live without restart. `id`/`authors` are
  server-forced (retrieval scoping invariant). `POST /personas/generate` (idempotent
  200/201, 403/502/504 failure modes); `PERSONA_AUTOGEN` + `PERSONA_GEN_TIMEOUT` knobs.
  First forged card (Marcus Aurelius, live-verified) is committed.
- **Persona detail view** (`/personas/{id}`): full card + linked works (manifest and
  uploads) via `GET /personas/{id}`; library speaker cards and author cells link there;
  "Start a conversation" preselects the persona on the main chat (`/?personas=`).
- **Upload pipeline** (`/upload` + `POST /library/uploads`): user texts
  (.txt/.md/.pdf/.epub — `pypdf`/`ebooklib`, magic-byte checks, 2 MB cap, per-IP limit)
  are validated, author-matched (deterministic: exact / folded-probable w/ 409 confirm /
  none), and embedded at request time. Texts live in `data/uploads/`, rows in SQLite
  `uploaded_works`, **merged with `corpus.yaml` at read time** — the curated manifest is
  never mutated at runtime. Uploaded works flow through library, reading room, sessions,
  and persona detail. No-match uploads **eagerly forge** their persona (non-fatal);
  confirmed name variants are appended to the card's `authors` (`add_author_variant`).
  Knobs: `UPLOAD_ENABLED`, `MAX_UPLOAD_MB`, `UPLOAD_TIMEOUT`; `ingest --uploads`
  re-indexes after `--reset`.

## Session log

### 2026-08-01 (night) — Persona detail view + upload pipeline

- Planned with the planner agent; user's four calls: **PDF/EPUB from the start**,
  **confirm-on-ambiguous**, **eager forge** at upload, **default limits** (2 MB cap,
  uploads enabled, in-memory rate limit).
- Phase 1: `GET /personas/{id}` (full card + works); `/personas/[id]` page (EN/中文
  toggle, works → reading room, "Start a conversation" → `/?personas=` preselect —
  `useSearchParams` inside Suspense, a Next 16 requirement); library speaker cards and
  corpus author cells became links.
- Phase 2: `POST /library/uploads` (multipart; txt/md/pdf/epub extraction via
  `pypdf`/`ebooklib`, magic-byte sniffing; 413/415/422 typed validation; 20/hr per-IP
  sliding-window 429). Texts → `data/uploads/`, metadata → SQLite `uploaded_works`
  (indexing → ready); `merge_works` unifies them with `corpus.yaml` at read time —
  **the curated manifest is never mutated at runtime**. Author match is deterministic
  (no LLM): exact → attach; folded probable → 409 + confirm (`"decline"` sentinel —
  FastAPI coerces empty form fields to `None`); none → persona-less. Ingest extracted
  to `ingest_text` (metadata gains `source`, `gutenberg_id` optional), runs via
  `asyncio.to_thread` + `wait_for`; failure cleans chunks + row + file. Sessions,
  works list, text endpoint, and `/personas/generate` all read the merged registry.
- Phase 3: eager `get_or_generate` on no-match (non-fatal — `persona_status`:
  created/existing/failed/skipped); `add_author_variant` (immutable `replace`) appends
  confirmed spellings to card `authors` so future matches are exact — YAML formatting
  is normalized on rewrite, content untouched. `ingest --uploads` re-indexes uploads
  after `--reset`.
- Coherence fix found in smoke: persona detail endpoint also merges uploads.
- Frontend: `/upload` page (tradition datalist, confirm panel, persona_status notes);
  library "+ Add a text" + "uploaded" chip — the library page stays English-hardcoded,
  so two planned i18n keys were dropped as dead code. Deps added: `pypdf`, `ebooklib`,
  `beautifulsoup4`, `python-multipart`.
- Tests: 129 backend (was 92; new `test_persona_detail.py`, `test_uploads.py` —
  hermetic PDF/EPUB fixtures built in-test, forge monkeypatched to tmp dirs so repo
  YAML is never mutated) + 34 frontend (was 22; first page-level tests). ruff / tsc /
  eslint / `next build` clean. Live smoke (isolated data dirs, autogen off): txt →
  6 chunks, pdf → exact Marcus match, merged list/text/session, 409/415 paths green.

### 2026-08-01 (evening) — Reading room + persona forge

- Planned with the planner agent, two rounds: user feedback — "the persona is always the
  work's author; if no card exists, create one and retrieve related sources through
  website" — turned the persona-less-works empty state into the forge.
- **Decisions**: full-text endpoint (no chapter splitting — Gutenberg headings too
  inconsistent); new hand-authored `plato.yaml` (Republic/Apology resolve to Plato, not
  Socrates, via most-specific-authors match; Socrates' card untouched so his retrieval
  keeps Plato's works); reading chats fully reuse sessions/SSE/traces with one nullable
  `sessions.work_id` column (same idempotent-ALTER pattern as `language`); MVP context
  awareness = client-side "ask about selection" (blockquote prefill, 2k-char cap);
  scroll-position awareness deferred.
- Backend: `persona_for_author()` (fewest-authors specificity, id tiebreak);
  `GET /library/works` gains `persona_id`; `GET /library/works/{id}/text` (sync def →
  threadpool; `load_work_text` downloads on cache miss, 404/502 modes); `persona_forge.py`
  (Wikipedia REST summary + one opensearch hop on miss/disambiguation, treated as
  untrusted input; `GeneratedCardFields` pydantic schema; per-author `asyncio.Lock`;
  teal excluded from generated colors — tutor identity); `POST /personas/generate`
  keyed by `work_id`; retrieval `where` gains `$and` with `{"work_id": ...}` (cache key
  already covers the where dict). `load_personas` parameterized by dir for hermetic tests.
- Frontend: `/read/[workId]` client page (`useParams`, sidesteps Next 16 async params);
  `ReaderPane` (paragraph split, selection→ask floating button, 2k cap with too-long hint);
  `ReaderChat` (summon flow: auto-POST → summoning → ready / failed+retry; lazy session
  create with `work_id`; same abort discipline as the chat page); dock toggle persisted
  to `localStorage`; mobile read/chat tabs; `Composer` gains optional `prefill` prop;
  library rows get "Read with {persona}" links; new `sky` theme for Plato.
- Live-verified: Republic text 1.19MB served with `persona_id: plato`; forge created
  `marcus_aurelius.yaml` via Wikipedia+DeepSeek in ~6s (201, repeat → 200, mapping live
  without restart); forged Marcus answered an anger question citing **only Meditations**
  passages — work-scoped retrieval confirmed end-to-end.
- Note: `marcus_aurelius.yaml` is a generated artifact — hand-edit or delete-to-regenerate.
- Two lint fixes forced by the new react-hooks eslint rules: dock state lazy-initializes
  from localStorage (no effect), summon effect sets state only in async callbacks.
- Ops: user's "Could not load the text (404)" was a **stale backend** on :8000 running
  pre-feature code (old routes 200, new route 404) — fixed by restarting; run dev with
  `--reload` to avoid this class of confusion.
- `.gitignore`: added `data/*.db-shm` / `data/*.db-wal` (WAL sidecars were untracked).
- Committed this session's work together with the previously uncommitted
  language + trace-board work (user's call, one commit).

### 2026-08-01 (late pm) — Housekeeping: dev tools off, repo public

- `frontend/next.config.ts`: `devIndicators: false` — hides the Next.js dev overlay
  (checked the bundled 16.2 docs: `appIsrStatus`/`buildActivity` were removed in v16).
- GitHub repo flipped to **public** ([maple3788/aloof_from_the_world](https://github.com/maple3788/aloof_from_the_world));
  pre-check confirmed `backend/.env` (DeepSeek key) is untracked + gitignored.
- Note: all language + trace-board work is **uncommitted locally** (29 files, +772/−107)
  — awaiting the user's call to commit/push.

### 2026-08-01 (pm) — Trace board: per-query pipeline observability

- Planned with the planner agent (decisions: cascade retention with session delete, board
  only for now — no chat→trace links, metadata+280-char excerpts only — no full prompts,
  aborted streams ARE traced).
- **Why not LangChain callbacks**: retrieval is a raw `similarity_search` inside Python
  nodes, invisible to tracers — so nodes record spans into a per-request `TraceRecorder`
  passed through graph state (`app/agents/trace.py`, modeled on `cache.py`'s NullCache).
  The graph stays DB-free; `chat.py` owns persistence on ok/error/`CancelledError` paths,
  try/except so trace failures never break SSE.
- Backend: `traces` table (scalar filter columns + JSON `detail`, `CREATE IF NOT EXISTS`
  covers legacy DBs — no ALTER needed); `Database.save_trace/list_traces/get_trace`;
  `delete_session` also clears traces; `api/traces.py` (list: session filter + limit/offset
  clamps; detail 404); SSE `done` carries `trace_id` (unused by UI yet).
- Frontend: `/traces` page + `TraceBoard` (expandable rows: translated query, retrieval
  doc excerpts, reply ms, critic verdict incl. cache-hit, error block); session filter
  select; page-local EN/中文 toggle; Sidebar link; `trace_id?` on the done StreamEvent.
- Tests: 63 backend (was 50) + 15 frontend (was 10); ruff/tsc/eslint/`next build` clean.
  Live-verified zh turn: translation span 1061 ms, persona-scoped Analects retrieval,
  critic flagged an overreach with a Chinese note.

### 2026-08-01 — Per-session language: English default, 中文

- Language is a **per-session setting** (same lifecycle as mode/personas): chosen in the
  sidebar for a new conversation, locked once created. `en` default, `zh` option.
- Backend: `app/agents/i18n.py` (`normalize_language`, `language_directive`,
  `retrieval_query`); `language` threaded through `AgentState` → router → persona/tutor
  system prompts (directive appended last) → critic (`note_language` in prompt; language
  is part of the critic cache key). zh turns translate the query to English once per turn
  before retrieval — the MiniLM embeddings are English-centric, so raw Chinese queries
  retrieved poorly. Translation failure falls back to the raw query.
- DB: `language` column in `SCHEMA` + idempotent `ALTER TABLE` migration in
  `Database.connect()` for pre-existing databases; `create_session(language=...)`.
  API: `SessionCreate.language` (normalized), SSE `start` event carries it,
  `/personas` exposes `greeting_zh`; CLI `--language en|zh`.
- Frontend: EN/中文 toggle in `PersonaPicker` (locked with the session); `lib/i18n.ts`
  dictionary localizes the chat chrome (sidebar, picker, composer, welcome, moderator
  note); welcome cards show `greeting_zh` in zh sessions; session rows get an EN/中文 badge.
- Tests: 50 backend (was 36; new `test_i18n.py`, zh graph translation/asserts, session
  language roundtrip, legacy-DB migration test) + 10 frontend (was 8). ruff / tsc /
  eslint / `next build` clean. Live-verified: zh Socrates replies in Chinese, quotes the
  English sources inline, critic note in Chinese.

### 2026-08-01 (am) — DeepSeek support via OPENAI_BASE_URL (retro-recorded)

- DeepSeek rides the existing `openai` provider: new `openai_base_url` setting
  (`config.py`) passed to `ChatOpenAI` (`llm.py`); `.env.example` documents the recipe
  (`LLM_PROVIDER=openai`, `OPENAI_BASE_URL=https://api.deepseek.com`, `deepseek-chat`).
  Same mechanism covers any OpenAI-compatible API (Moonshot, DashScope, ...).
  Embeddings unchanged → no re-ingestion. User runs hosted DeepSeek as the default LLM.

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
- **L3/L4** Persona YAML: validate at startup with friendly errors. Runtime-forged cards
  go live without restart (forge busts the cache); **manually dropped YAML files still
  need a restart** (`load_personas` is `lru_cache`d).

Deferred by user decision (2026-08-01):

- **Chat→trace linking**: SSE `done` already carries `trace_id`; needs a nullable
  `messages.trace_id` column + a "view trace" link in `MessageList`/`page.tsx`.
- **TRACE_FULL_PROMPTS**: persist full system prompts in trace detail for prompt
  debugging (currently metadata + 280-char excerpts only).

Reading-room stretch (deferred 2026-08-01):

- Scroll-position/chapter awareness (needs reliable heading detection on inconsistent
  Gutenberg texts + a context-injection contract).
- Drag-resize splitter (fixed 60/40 + dock toggle for now); reading-position persistence.
- `work_id` on trace rows + trace filtering by work; shared `useChatStream` hook
  (token accumulation is duplicated between `page.tsx` and `ReaderChat`).

Upload pipeline follow-ups (deferred 2026-08-01):

- **No edit/delete UI** for uploads or personas — manual removal: delete the
  `data/uploads/*.txt` file + its `uploaded_works` row, then `ingest --reset --uploads`
  (or `delete_work_chunks` for the id).
- LLM metadata inference (prefill the upload form from content) — the planned optional
  piece, skipped to keep author-matching deterministic.
- Duplicate-content detection; PDFs larger than 2 MB need a `MAX_UPLOAD_MB` bump.
- Wrong-author uploads forge junk personas under eager mode — mitigated by the confirm
  step; cleanup is manual (see above).

Watch:

- DeepSeek gave a 36-char reply on one live zh turn (2026-08-01) — if terseness
  persists, tune persona prompts or try `deepseek-reasoner`; the trace board makes
  reply length visible per turn.

## Pointers

- Config/env reference: `backend/.env.example`
- Architecture review canvas: see session log above
- Agent definitions: `.cursor/agents/` (architect is read-only; use for design reviews)
