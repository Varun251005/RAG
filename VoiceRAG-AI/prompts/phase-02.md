# Phase 02 — Backend Foundation

## Goal

A fully runnable FastAPI application with configuration management, database connectivity, structured logging, error handling, dependency injection, and a health check endpoint. No feature logic yet.

---

## Deliverables

### `app/core/config.py`
- Pydantic `BaseSettings` class
- Loads all env vars from `.env`
- Typed fields for: `APP_ENV`, `APP_SECRET_KEY`, `DATABASE_URL`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_EMBEDDING_MODEL`, `CHROMA_HOST`, `CHROMA_PORT`, `CHROMA_COLLECTION`, `EDGE_TTS_VOICE`, `ALLOWED_ORIGINS`
- Singleton `get_settings()` function (lru_cache)

### `app/core/logging.py`
- Loguru-based structured logging setup
- JSON format in production, human-readable in development
- `setup_logging()` function called on startup

### `app/core/exceptions.py`
- Base `AppException(Exception)` with `status_code`, `message`, `detail`
- Specific: `NotFoundError`, `ValidationError`, `ServiceError`, `ConflictError`
- `register_exception_handlers(app)` — attaches handlers to FastAPI app

### `app/db/base.py`
- SQLAlchemy `DeclarativeBase` subclass
- `TimestampMixin` with `created_at`, `updated_at` columns (auto UTC)

### `app/db/session.py`
- `AsyncEngine` created from `settings.DATABASE_URL`
- `AsyncSessionLocal` factory
- `get_db()` async generator — yields `AsyncSession`, used as `Depends`

### `app/api/deps.py`
- `get_db` re-exported for use in routes
- Placeholder factories for future services (empty, typed)

### `app/api/v1/health.py`
```
GET /api/v1/health
Response: { "status": "ok", "env": "development", "version": "0.1.0" }
```
- Checks DB connectivity
- Checks ChromaDB connectivity
- Returns degraded status if dependencies are unreachable (200 still, with detail)

### `app/main.py`
- `create_app()` factory function
- Registers: CORS middleware, exception handlers, API router (v1)
- Calls `setup_logging()` on startup lifespan
- Mounts `/api/v1` prefix

---

## Success Criteria

- [ ] `GET /api/v1/health` returns `200 {"status": "ok"}`
- [ ] Application starts without errors via `uvicorn app.main:app`
- [ ] Settings are correctly loaded from `.env`
- [ ] A bad DB URL results in a `degraded` health response, not a crash
- [ ] Loguru outputs structured logs on each request
