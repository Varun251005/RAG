# Phase Review Checklist

Use this checklist after completing each phase to ensure quality and consistency before moving to the next.

---

## General (All Phases)

- [ ] All new files match the directory structure defined in `architecture.md`
- [ ] No business logic is placed inside API route handlers
- [ ] All Python functions have full type annotations
- [ ] All TypeScript code has explicit types — no `any`
- [ ] No hardcoded secrets, URLs, or credentials
- [ ] No unused imports, variables, or files
- [ ] No duplicate logic — shared code is extracted to utils or base classes
- [ ] All error cases are handled explicitly with appropriate HTTP status codes
- [ ] Environment variables are documented in `.env.example` / `.env.local.example`

---

## Backend Review

- [ ] Pydantic models are used for all request/response I/O
- [ ] All DB access goes through repository classes only
- [ ] All services are injected via `Depends()` — not instantiated in routes
- [ ] All async functions are properly awaited — no blocking calls
- [ ] Alembic migration added for any new DB table or column
- [ ] Custom exceptions from `core/exceptions.py` are used — not generic `Exception`
- [ ] Loguru logs are present at appropriate points (info, warning, error)

---

## Frontend Review

- [ ] Components use explicit TypeScript prop interfaces
- [ ] API calls are centralized in `lib/api/` — not scattered in components
- [ ] `'use client'` directive is present only where required
- [ ] All API response types match backend Pydantic schemas
- [ ] Loading and error states are handled in every data-fetching component
- [ ] No hardcoded API URLs — use `NEXT_PUBLIC_API_URL` env var

---

## Phase-Specific Checks

### Phase 01 — Scaffolding
- [ ] `docker-compose up` starts all 4 services cleanly
- [ ] No import errors on backend start
- [ ] Frontend dev server starts (`next dev`)
- [ ] Directory structure matches `architecture.md` exactly

### Phase 02 — Backend Foundation
- [ ] `GET /api/v1/health` returns `200 {"status": "ok"}`
- [ ] Settings load correctly from `.env`
- [ ] DB connectivity is verified in health check
- [ ] Loguru structured logs appear on each request

### Phase 03 — Document Ingestion
- [ ] PDF upload returns `DocumentResponse` with `status=READY`
- [ ] Vectors stored in ChromaDB and queryable
- [ ] PostgreSQL `documents` table populated correctly
- [ ] Invalid file type returns `400`
- [ ] Delete removes from both PostgreSQL and ChromaDB

### Phase 04 — RAG Pipeline
- [ ] Query endpoint returns answer with source citations
- [ ] Answer is grounded in retrieved chunks (not hallucinated)
- [ ] Empty result set returns graceful response (not 500)

### Phase 05 — Voice Layer
- [ ] Audio blob transcribed to text correctly
- [ ] Text synthesized to audio stream using Edge-TTS
- [ ] Audio response plays in the browser

### Phase 06 — Frontend Foundation
- [ ] All pages render without console errors
- [ ] API client properly handles network errors
- [ ] Zustand stores initialize without errors

### Phase 07–09 — Feature UI
- [ ] Upload flow works end-to-end in browser
- [ ] Chat flow works end-to-end in browser
- [ ] Voice record → transcribe → answer → playback works end-to-end

### Phase 10 — Integration & Polish
- [ ] No broken flows in the full user journey
- [ ] Error messages are user-friendly (not stack traces)
- [ ] Loading states prevent duplicate submissions

### Phase 11 — Testing
- [ ] All tests pass: `pytest` (backend), `vitest` (frontend)
- [ ] Coverage reported for services and repositories

### Phase 12 — Production Hardening
- [ ] `docker-compose.prod.yml` builds and starts cleanly
- [ ] Rate limiting is in effect on ingestion and query endpoints
- [ ] `README.md` covers: prerequisites, setup, env config, running, testing
