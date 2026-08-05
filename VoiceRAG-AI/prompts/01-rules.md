# VoiceRAG AI — Engineering Rules

## General Rules

1. Never place business logic inside API route handlers
2. Never access the database directly from routes or services — use repositories
3. Never hardcode configuration values; use environment variables
4. Never use `any` in TypeScript
5. Never leave unused imports, variables, or files
6. Never duplicate logic — extract shared code into utilities or base classes
7. Always handle errors explicitly — no silent failures
8. Always use async/await throughout the backend
9. Always validate input with Pydantic (backend) or Zod (frontend)
10. Always write typed function signatures — no implicit types

---

## Backend Rules (Python / FastAPI)

### Structure
- Each module has a single responsibility
- Route files import from services only — never from repositories or DB directly
- Service files import from repositories and external adapters
- Repository files interact with DB/VectorStore only

### Typing
- Every function must have fully annotated parameters and return types
- Use Pydantic `BaseModel` for all request and response schemas
- Use `Optional[T]` or `T | None` (Python 3.10+ union syntax)

### Error Handling
- Define custom exception classes in `core/exceptions.py`
- Register exception handlers in `main.py`
- Never raise generic `Exception` — use specific types
- Return structured error responses: `{ "error": "...", "detail": "..." }`

### Database
- Use SQLAlchemy async sessions
- All DB access goes through the repository pattern
- Migrations managed by Alembic — never use `create_all()` in production
- Use `AsyncSession` with `async with` context managers

### Dependency Injection
```python
# Correct
async def get_documents(service: DocumentService = Depends(get_document_service)):
    ...

# Wrong — never instantiate services inside routes
async def get_documents():
    service = DocumentService(db=...)  # ❌
```

### Naming Conventions
- Files: `snake_case.py`
- Classes: `PascalCase`
- Functions / Variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Pydantic models: `PascalCase` + suffix (`DocumentCreate`, `DocumentResponse`)

---

## Frontend Rules (Next.js / TypeScript)

### Structure
- Pages live in `app/` using App Router conventions
- Reusable UI lives in `components/`
- API calls are centralized in `lib/api/`
- State is managed in `store/` via Zustand
- Shared types live in `types/`
- Custom hooks live in `hooks/`

### Typing
- All component props must have explicit TypeScript interfaces
- All API response types must match backend Pydantic schemas
- No `any` — use `unknown` and narrow types explicitly

### Components
- Every component is a named export, not default (except pages)
- Props interfaces are defined above the component in the same file
- No business logic inside components — delegate to hooks or `lib/`
- Use `'use client'` only when necessary (prefer Server Components)

### API Client
```typescript
// Correct — centralized API call
import { fetchDocuments } from '@/lib/api/documents'

// Wrong — fetch directly in component
const res = await fetch('/api/documents') // ❌
```

### Naming Conventions
- Files: `PascalCase.tsx` for components, `camelCase.ts` for utilities/hooks
- Components: `PascalCase`
- Hooks: `useFeatureName`
- Types/Interfaces: `PascalCase` (no `I` prefix)
- Zustand stores: `useFeatureStore`

---

## Git Rules

- One commit per phase, descriptive message
- Format: `feat(phase-XX): description`
- No commits with broken tests or linting errors
- Never commit `.env` files

---

## File Organization Rules

- Do not create files unless they are needed by the current phase
- Do not leave placeholder or TODO files — implement or defer
- Keep each file under 300 lines where possible; split if larger
- Co-locate tests with the module they test (`test_document_service.py` next to `document_service.py`)
