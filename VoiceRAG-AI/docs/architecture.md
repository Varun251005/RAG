# VoiceRAG AI — System Architecture

## Overview

VoiceRAG AI is a production-grade, voice-enabled Retrieval-Augmented Generation (RAG) system. Users can upload documents, ask questions via voice or text, and receive spoken AI-generated answers grounded in their documents.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          CLIENT (Browser)                           │
│              Next.js 15 · React 19 · TypeScript · shadcn/ui         │
└────────────────────────┬────────────────────────────────────────────┘
                         │ HTTPS / WebSocket
┌────────────────────────▼────────────────────────────────────────────┐
│                       BACKEND (FastAPI)                             │
│                                                                     │
│   ┌─────────────┐  ┌──────────────┐  ┌─────────────────────────┐   │
│   │  API Layer  │  │ Service Layer│  │     Core Modules        │   │
│   │  (routes)   │→ │  (business   │→ │  RAG · Voice · DB       │   │
│   │             │  │   logic)     │  │  VectorStore · Auth      │   │
│   └─────────────┘  └──────────────┘  └─────────────────────────┘   │
│                                                                     │
└──────┬────────────────────┬──────────────────────┬─────────────────┘
       │                    │                      │
┌──────▼──────┐   ┌─────────▼──────────┐  ┌───────▼──────┐
│ PostgreSQL  │   │     ChromaDB       │  │  Gemini API  │
│ (metadata,  │   │  (vector store,    │  │  (LLM, embed)│
│  sessions,  │   │   embeddings)      │  └──────────────┘
│  users)     │   └────────────────────┘
└─────────────┘
```

---

## Architectural Principles

| Principle         | Application                                                        |
|-------------------|--------------------------------------------------------------------|
| Clean Architecture| Strict layer separation: API → Services → Core → Infrastructure   |
| SOLID             | Single responsibility per class; open/closed via abstractions      |
| DI                | Services injected via FastAPI `Depends()` and factory functions    |
| Typed             | Full type annotations in Python (Pydantic) and TypeScript          |
| No Duplication    | Shared utilities, base classes, and reusable components            |
| Env-Driven Config | All secrets and settings via `.env` + Pydantic `BaseSettings`      |

---

## Backend Layer Breakdown

```
backend/
├── app/
│   ├── api/                  # Route handlers only — no business logic
│   │   ├── v1/
│   │   │   ├── documents.py
│   │   │   ├── query.py
│   │   │   ├── voice.py
│   │   │   └── health.py
│   │   └── deps.py           # Dependency injection factories
│   │
│   ├── services/             # All business logic lives here
│   │   ├── document_service.py
│   │   ├── rag_service.py
│   │   ├── voice_service.py
│   │   └── embedding_service.py
│   │
│   ├── core/                 # Cross-cutting concerns
│   │   ├── config.py         # Pydantic BaseSettings
│   │   ├── logging.py
│   │   ├── exceptions.py
│   │   └── security.py
│   │
│   ├── models/               # Pydantic schemas (request/response)
│   │   ├── document.py
│   │   ├── query.py
│   │   └── voice.py
│   │
│   ├── db/                   # Database layer
│   │   ├── base.py           # SQLAlchemy base
│   │   ├── session.py        # Async session factory
│   │   └── repositories/     # Repository pattern
│   │       ├── document_repo.py
│   │       └── session_repo.py
│   │
│   ├── vector_store/         # ChromaDB abstraction
│   │   ├── chroma_client.py
│   │   └── vector_repo.py
│   │
│   ├── rag/                  # RAG pipeline
│   │   ├── pipeline.py       # Orchestrates retrieval + generation
│   │   ├── retriever.py
│   │   └── generator.py
│   │
│   ├── voice/                # TTS / STT
│   │   ├── tts.py            # Edge-TTS wrapper
│   │   └── stt.py            # STT integration
│   │
│   └── utils/                # Pure utility functions
│       ├── file_utils.py
│       └── text_utils.py
│
├── migrations/               # Alembic migrations
├── tests/
├── Dockerfile
├── pyproject.toml
└── .env.example
```

---

## Frontend Layer Breakdown

```
frontend/
├── src/
│   ├── app/                  # Next.js 15 App Router
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   ├── documents/
│   │   │   └── page.tsx
│   │   └── chat/
│   │       └── page.tsx
│   │
│   ├── components/           # Reusable UI components
│   │   ├── ui/               # shadcn/ui base components
│   │   ├── document/
│   │   │   ├── UploadDropzone.tsx
│   │   │   └── DocumentList.tsx
│   │   ├── chat/
│   │   │   ├── ChatWindow.tsx
│   │   │   ├── MessageBubble.tsx
│   │   │   └── VoiceInput.tsx
│   │   └── layout/
│   │       ├── Sidebar.tsx
│   │       └── Navbar.tsx
│   │
│   ├── hooks/                # Custom React hooks
│   │   ├── useVoiceRecorder.ts
│   │   ├── useDocuments.ts
│   │   └── useChat.ts
│   │
│   ├── lib/                  # API clients and utilities
│   │   ├── api/
│   │   │   ├── client.ts     # Axios/fetch base client
│   │   │   ├── documents.ts
│   │   │   └── chat.ts
│   │   └── utils.ts
│   │
│   ├── types/                # Shared TypeScript types
│   │   ├── document.ts
│   │   └── chat.ts
│   │
│   └── store/                # Zustand state management
│       ├── documentStore.ts
│       └── chatStore.ts
│
├── public/
├── Dockerfile
├── next.config.ts
├── tailwind.config.ts
└── .env.local.example
```

---

## Data Flow

### Document Ingestion
```
User uploads PDF
  → Frontend: UploadDropzone → POST /api/v1/documents
  → Backend: DocumentService.ingest()
      → PyMuPDF: extract text + metadata
      → EmbeddingService: chunk + embed via Gemini
      → VectorRepo: store in ChromaDB
      → DocumentRepo: persist metadata in PostgreSQL
  → Response: document ID + status
```

### Voice Query RAG Flow
```
User speaks
  → VoiceInput: MediaRecorder captures audio blob
  → POST /api/v1/voice/transcribe → STT → text
  → POST /api/v1/query { question, document_ids }
  → RAGService.query()
      → Retriever: embed question → ChromaDB similarity search
      → Generator: Gemini LLM with retrieved context
      → Response: answer text + sources
  → POST /api/v1/voice/synthesize { text }
      → VoiceService: Edge-TTS → audio stream
  → Frontend plays audio
```

---

## Infrastructure

| Component   | Technology          | Purpose                        |
|-------------|---------------------|--------------------------------|
| Containerize| Docker + Compose    | Reproducible environments      |
| DB          | PostgreSQL 16       | User data, documents, sessions |
| Vector DB   | ChromaDB            | Embeddings + similarity search |
| LLM         | Gemini API          | Generation + Embeddings        |
| TTS         | Edge-TTS            | Voice synthesis (offline-capable) |
| Package Mgr | uv                  | Fast Python dependency management |

---

## Environment Variables

```env
# App
APP_ENV=development
APP_SECRET_KEY=

# Gemini
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.0-flash
GEMINI_EMBEDDING_MODEL=text-embedding-004

# PostgreSQL
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/voicerag

# ChromaDB
CHROMA_HOST=localhost
CHROMA_PORT=8000
CHROMA_COLLECTION=voicerag

# TTS
EDGE_TTS_VOICE=en-US-AriaNeural

# CORS
ALLOWED_ORIGINS=http://localhost:3000
```
