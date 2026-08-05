# VoiceRAG AI — Implementation Roadmap

## Phases Overview

| Phase | Title                     | Deliverable                                      | Status   |
|-------|---------------------------|--------------------------------------------------|----------|
| 01    | Project Scaffolding       | Repo structure, configs, Docker, env setup       | ⏳ Pending |
| 02    | Backend Foundation        | FastAPI app, DB, config, health endpoint         | ⏳ Pending |
| 03    | Document Ingestion        | PDF parsing, chunking, embedding, vector store   | ⏳ Pending |
| 04    | RAG Pipeline              | Retriever + Gemini generator + query API         | ⏳ Pending |
| 05    | Voice Layer               | STT input + Edge-TTS synthesis API               | ⏳ Pending |
| 06    | Frontend Foundation       | Next.js app, layout, routing, API client         | ⏳ Pending |
| 07    | Document UI               | Upload dropzone, document list, status tracking  | ⏳ Pending |
| 08    | Chat UI                   | Chat window, message bubbles, streaming response | ⏳ Pending |
| 09    | Voice UI                  | Voice recorder, playback, waveform animation     | ⏳ Pending |
| 10    | Integration & Polish      | End-to-end flow, error handling, loading states  | ⏳ Pending |
| 11    | Testing                   | Unit + integration tests (pytest + Jest/Vitest)  | ⏳ Pending |
| 12    | Production Hardening      | Docker Compose, logging, rate limiting, security | ⏳ Pending |

---

## Phase 01 — Project Scaffolding

**Goal:** Establish the full directory structure and configuration baseline for both backend and frontend before any feature code is written.

### Backend
- [ ] Initialize Python project with `uv`
- [ ] `pyproject.toml` with all dependencies declared
- [ ] `Dockerfile` (multi-stage, Python 3.12)
- [ ] `.env.example` with all required variables
- [ ] Alembic setup for migrations
- [ ] `docker-compose.yml` (app, postgres, chromadb)

### Frontend
- [ ] `create-next-app` with TypeScript, App Router, Tailwind
- [ ] Install shadcn/ui and configure
- [ ] `Dockerfile` (multi-stage, Node 20)
- [ ] `.env.local.example`
- [ ] ESLint + Prettier config
- [ ] Path aliases (`@/`) configured

---

## Phase 02 — Backend Foundation

**Goal:** Runnable FastAPI application with config, DB connection, and health endpoint.

- [ ] `core/config.py` — Pydantic `BaseSettings`
- [ ] `core/logging.py` — Structured logging
- [ ] `core/exceptions.py` — Custom exception classes + handlers
- [ ] `db/session.py` — Async SQLAlchemy session factory
- [ ] `db/base.py` — Declarative base + common mixins
- [ ] `api/v1/health.py` — `GET /api/v1/health`
- [ ] `api/deps.py` — Dependency injection factories
- [ ] `main.py` — App factory with middleware

---

## Phase 03 — Document Ingestion

**Goal:** Full pipeline to upload a PDF, extract text, chunk, embed, and store.

- [ ] `models/document.py` — Pydantic request/response schemas
- [ ] `db/repositories/document_repo.py` — Async CRUD
- [ ] `utils/file_utils.py` — PDF parsing with PyMuPDF
- [ ] `utils/text_utils.py` — Chunking strategies
- [ ] `services/embedding_service.py` — Gemini embedding wrapper
- [ ] `vector_store/chroma_client.py` — ChromaDB async client
- [ ] `vector_store/vector_repo.py` — Vector CRUD abstraction
- [ ] `services/document_service.py` — Orchestrates ingestion pipeline
- [ ] `api/v1/documents.py` — Upload + list + delete endpoints

---

## Phase 04 — RAG Pipeline

**Goal:** Accept a question, retrieve context, generate a grounded answer.

- [ ] `rag/retriever.py` — Vector similarity search
- [ ] `rag/generator.py` — Gemini LLM generation with context
- [ ] `rag/pipeline.py` — Orchestrates retriever + generator
- [ ] `models/query.py` — Query request/response schemas
- [ ] `services/rag_service.py` — Business logic for query handling
- [ ] `api/v1/query.py` — `POST /api/v1/query`

---

## Phase 05 — Voice Layer

**Goal:** Transcribe audio input and synthesize spoken responses.

- [ ] `voice/stt.py` — Speech-to-text (Whisper / Gemini audio)
- [ ] `voice/tts.py` — Edge-TTS async streaming wrapper
- [ ] `models/voice.py` — Voice request/response schemas
- [ ] `services/voice_service.py` — STT + TTS orchestration
- [ ] `api/v1/voice.py` — `/transcribe` and `/synthesize` endpoints

---

## Phase 06 — Frontend Foundation

**Goal:** Runnable Next.js app with layout, routing, and typed API client.

- [ ] `app/layout.tsx` — Root layout with font, theme provider
- [ ] `app/page.tsx` — Landing / redirect
- [ ] `components/layout/Navbar.tsx`
- [ ] `components/layout/Sidebar.tsx`
- [ ] `lib/api/client.ts` — Base HTTP client with error handling
- [ ] `types/document.ts`, `types/chat.ts`
- [ ] Zustand stores scaffolded

---

## Phase 07 — Document UI

**Goal:** Users can upload PDFs and see their document library.

- [ ] `components/document/UploadDropzone.tsx`
- [ ] `components/document/DocumentList.tsx`
- [ ] `hooks/useDocuments.ts`
- [ ] `lib/api/documents.ts`
- [ ] `app/documents/page.tsx`

---

## Phase 08 — Chat UI

**Goal:** Text-based chat with streaming response display.

- [ ] `components/chat/ChatWindow.tsx`
- [ ] `components/chat/MessageBubble.tsx`
- [ ] `hooks/useChat.ts`
- [ ] `lib/api/chat.ts`
- [ ] `app/chat/page.tsx`

---

## Phase 09 — Voice UI

**Goal:** Record voice, transcribe, query, and play back answer.

- [ ] `components/chat/VoiceInput.tsx` — Record + waveform
- [ ] `hooks/useVoiceRecorder.ts` — MediaRecorder abstraction
- [ ] Audio playback integration in `ChatWindow`

---

## Phase 10 — Integration & Polish

**Goal:** Full end-to-end flow works reliably with good UX.

- [ ] Error boundaries and toast notifications
- [ ] Loading skeletons and spinners
- [ ] Source citations displayed per answer
- [ ] Mobile responsive layout
- [ ] Streaming text display from backend SSE

---

## Phase 11 — Testing

**Goal:** Confidence that the system behaves correctly.

- [ ] `pytest` + `httpx` for backend API tests
- [ ] Service-level unit tests with mocked dependencies
- [ ] Vitest + React Testing Library for frontend
- [ ] Test coverage reporting

---

## Phase 12 — Production Hardening

**Goal:** Ready to deploy.

- [ ] Rate limiting (slowapi)
- [ ] Request validation + sanitization
- [ ] Structured JSON logging (loguru)
- [ ] `docker-compose.prod.yml`
- [ ] Health checks + graceful shutdown
- [ ] `README.md` with full setup guide
