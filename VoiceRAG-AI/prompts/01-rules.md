# VoiceRAG AI — Engineering Rules

> These rules apply to every file, every phase, without exception.

---

## Core Coding Rules

| # | Rule |
|---|------|
| 1 | **Always use `async` functions** — no synchronous I/O anywhere in the stack |
| 2 | **Always use type hints** — every parameter and return value must be annotated |
| 3 | **Always use logging** — use `loguru` (backend) / `console` structured (frontend); no bare `print()` |
| 4 | **Handle exceptions properly** — use typed custom exceptions; never swallow errors silently |
| 5 | **Use Pydantic models** — all data in/out of services and APIs must be Pydantic-validated |
| 6 | **Keep functions below 40 lines** — if a function grows larger, extract sub-functions |
| 7 | **Separate API from services** — routes call services; services contain all logic |
| 8 | **No hardcoded API keys** — zero credentials in source code, ever |
| 9 | **Use `.env`** — all environment-specific config loaded via Pydantic `BaseSettings` |
| 10 | **Create reusable components** — abstract shared patterns into utilities, base classes, hooks |
| 11 | **Comment only where necessary** — self-explanatory code needs no comments; explain *why*, not *what* |
| 12 | **Write production-quality code** — no TODOs, no stubs, no placeholder logic in committed code |
| 13 | **Never use deprecated libraries** — always use the actively maintained, recommended API |
| 14 | **Always explain generated files** — every new file must be accompanied by a clear explanation of its purpose and responsibility |

---

## General Architecture Rules

1. Never place business logic inside API route handlers
2. Never access the database directly from routes — use repositories
3. Never instantiate services manually inside routes — use `Depends()`
4. Never duplicate logic — extract shared code into utilities or base classes
5. Never leave unused imports, variables, or files
6. Always validate input at the API boundary with Pydantic (backend) or Zod (frontend)
7. Always write typed function signatures — no implicit types

---

## Backend Rules (Python / FastAPI)

### Async

```python
# ✅ Correct
async def get_document(doc_id: str, repo: DocumentRepository = Depends(get_doc_repo)) -> DocumentResponse:
    return await repo.get_by_id(doc_id)

# ❌ Wrong — synchronous in an async service
def get_document(doc_id: str) -> DocumentResponse:
    return repo.get_by_id(doc_id)
```

### Type Hints

- Every function parameter and return type must be annotated
- Use `str | None` (Python 3.10+ union syntax), not `Optional[str]`
- Use `list[T]`, `dict[K, V]` — not bare `list` or `dict`

### Logging

```python
from loguru import logger

# ✅ Correct
logger.info("Ingesting document", filename=filename, size=len(file_bytes))
logger.error("Embedding failed", doc_id=doc_id, error=str(e))

# ❌ Wrong
print(f"Ingesting {filename}")
```

### Exception Handling

```python
# ✅ Correct — typed, logged, re-raised as domain exception
try:
    result = await embedding_service.embed(chunks)
except GoogleAPIError as e:
    logger.error("Gemini embedding failed", error=str(e))
    raise ServiceError("Embedding failed") from e

# ❌ Wrong — silent swallow
try:
    result = await embedding_service.embed(chunks)
except Exception:
    pass
```

- Define all custom exceptions in `core/exceptions.py`
- Register handlers in `main.py`
- Return structured JSON errors: `{ "error": "...", "detail": "..." }`
- Never raise bare `Exception`

### Pydantic Models

- All service inputs/outputs use Pydantic `BaseModel`
- Request schemas: `DocumentCreate`, `QueryRequest`
- Response schemas: `DocumentResponse`, `QueryResponse`
- ORM models use `model_config = ConfigDict(from_attributes=True)`

### Function Length

```python
# ✅ Correct — each step extracted
async def ingest(self, file_bytes: bytes, filename: str) -> DocumentResponse:
    self._validate_pdf(file_bytes)
    chunks = await self._extract_and_chunk(file_bytes)
    embeddings = await self._embed(chunks)
    await self._store(embeddings, chunks, filename)
    return await self._save_metadata(filename, len(chunks))

# ❌ Wrong — 80-line monolith doing everything in one function
```

### Dependency Injection

```python
# ✅ Correct
async def query(request: QueryRequest, service: RAGService = Depends(get_rag_service)):
    return await service.answer(request)

# ❌ Wrong
async def query(request: QueryRequest):
    db = AsyncSession(...)
    service = RAGService(db=db)  # never do this in a route
```

### Database

- Use SQLAlchemy async sessions via `AsyncSession`
- All DB access through repository classes only
- Migrations via Alembic — never `Base.metadata.create_all()` in production
- Use `async with session.begin()` for transactions

### Environment Variables

```python
# ✅ Correct
class Settings(BaseSettings):
    gemini_api_key: str
    database_url: str

    model_config = SettingsConfigDict(env_file=".env")

# ❌ Wrong
GEMINI_API_KEY = "AIza..."  # hardcoded secret
```

### Naming Conventions

| Element | Convention | Example |
|---|---|---|
| Files | `snake_case.py` | `document_service.py` |
| Classes | `PascalCase` | `DocumentService` |
| Functions / Variables | `snake_case` | `get_document` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_CHUNK_SIZE` |
| Pydantic schemas | `PascalCase` + purpose suffix | `DocumentCreate`, `DocumentResponse` |

---

## Frontend Rules (Next.js / TypeScript)

### Async

- All data fetching uses `async/await`
- `useEffect` with async must use an inner async function — no async effect directly

### Type Hints

- All component props have explicit TypeScript interfaces
- No `any` — use `unknown` with type narrowing if truly unknown
- All API response types mirror backend Pydantic schemas

### Logging

- Use structured `console.error` / `console.warn` with context objects
- Never use bare `console.log` in production code

### Exception Handling

- Wrap API calls in `try/catch`; surface errors via toast or error state
- Use an error boundary for unexpected component crashes
- Never let unhandled promise rejections reach the user silently

### Pydantic ↔ TypeScript

```typescript
// Backend: DocumentResponse Pydantic model → Frontend TypeScript type
export interface DocumentResponse {
  id: string
  filename: string
  status: 'PROCESSING' | 'READY' | 'FAILED'
  page_count: number
  created_at: string
}
```

### Function / Component Length

- Keep components under 100 lines — extract sub-components or hooks
- Keep hook functions under 40 lines — split logic into helpers

### Component Rules

- Named exports only (except page files)
- Props interface defined above the component
- No business logic in components — delegate to hooks or `lib/api/`
- `'use client'` only when required (prefer Server Components)

### API Client

```typescript
// ✅ Correct — centralized
import { uploadDocument } from '@/lib/api/documents'

// ❌ Wrong — inline fetch in component
const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/documents`)
```

### Environment Variables

```typescript
// ✅ Correct — from env
const apiUrl = process.env.NEXT_PUBLIC_API_URL

// ❌ Wrong — hardcoded
const apiUrl = 'http://localhost:8000'
```

### Naming Conventions

| Element | Convention | Example |
|---|---|---|
| Component files | `PascalCase.tsx` | `ChatWindow.tsx` |
| Utility / Hook files | `camelCase.ts` | `useVoiceRecorder.ts` |
| Components | `PascalCase` | `MessageBubble` |
| Hooks | `useFeatureName` | `useDocuments` |
| Types / Interfaces | `PascalCase` (no `I` prefix) | `DocumentResponse` |
| Zustand stores | `useFeatureStore` | `useDocumentStore` |

---

## File Generation Rule

> Every file created during any phase must be accompanied by a plain-English explanation of:
> 1. **What the file is** — its module name and type
> 2. **Why it exists** — its single responsibility in the system
> 3. **What it depends on** — direct imports and injected dependencies
> 4. **What depends on it** — which layer calls or imports it

This ensures no mystery files and maintains full architectural traceability.

---

## Git Rules

- One commit per completed phase
- Format: `feat(phase-XX): short description`
- No commits with failing tests or linting errors
- Never commit `.env`, `.env.local`, or any file containing secrets

---

## File Organization Rules

- Do not create a file unless it is needed by the current phase
- Keep files under 300 lines — split by responsibility if larger
- Keep functions under 40 lines — extract helpers if needed
- Co-locate tests with the module they test
