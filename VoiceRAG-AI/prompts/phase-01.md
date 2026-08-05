# Phase 01 — Project Scaffolding

## Goal

Establish the complete directory structure and configuration baseline for both backend and frontend. No feature code is written in this phase — only project skeleton, tooling, and Docker infrastructure.

---

## Backend Deliverables

### 1. `pyproject.toml`
- Project metadata (name, version, Python `>=3.12`)
- Dependencies:
  - `fastapi`, `uvicorn[standard]`
  - `sqlalchemy[asyncio]`, `asyncpg`, `alembic`
  - `chromadb`
  - `langchain`, `langchain-google-genai`
  - `google-generativeai`
  - `pymupdf`
  - `edge-tts`
  - `pydantic-settings`
  - `python-multipart`
  - `loguru`
  - `slowapi`
- Dev dependencies:
  - `pytest`, `pytest-asyncio`, `httpx`
  - `ruff`, `mypy`

### 2. `.env.example`
All required environment variables with placeholder values (no real secrets).

### 3. Directory skeleton
```
backend/
├── app/
│   ├── api/v1/
│   ├── core/
│   ├── db/repositories/
│   ├── models/
│   ├── rag/
│   ├── services/
│   ├── utils/
│   ├── vector_store/
│   └── voice/
├── migrations/
├── tests/
├── Dockerfile
└── pyproject.toml
```

### 4. `Dockerfile` (backend)
- Multi-stage build
- Base: `python:3.12-slim`
- Use `uv` for installation
- Non-root user

### 5. Alembic init
- `alembic.ini` + `migrations/env.py` configured for async SQLAlchemy

---

## Frontend Deliverables

### 1. Next.js 15 init
- TypeScript, App Router, Tailwind CSS, ESLint
- Strict TypeScript config

### 2. shadcn/ui setup
- Initialize with default style
- Install base components: `button`, `card`, `input`, `toast`, `dialog`, `badge`

### 3. Additional dependencies
- `zustand` — state management
- `axios` — HTTP client
- `zod` — schema validation
- `lucide-react` — icons
- `class-variance-authority`, `clsx`, `tailwind-merge`

### 4. `.env.local.example`
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 5. `Dockerfile` (frontend)
- Multi-stage: builder + runner
- Base: `node:20-alpine`

### 6. Path aliases
`tsconfig.json` configured with `@/*` pointing to `src/*`

---

## Docker Compose Deliverable

### `docker-compose.yml`
Services:
- `backend` — FastAPI app on port 8000
- `frontend` — Next.js app on port 3000
- `postgres` — PostgreSQL 16 with health check
- `chromadb` — ChromaDB on port 8000 (internal)

Shared network, named volumes for data persistence.

---

## Success Criteria

- [ ] `docker-compose up` starts all services without errors
- [ ] Backend container starts (no app yet, just uvicorn imported)
- [ ] Frontend container starts (`next dev` runs)
- [ ] PostgreSQL and ChromaDB containers are healthy
- [ ] All directories exist as specified in architecture.md
