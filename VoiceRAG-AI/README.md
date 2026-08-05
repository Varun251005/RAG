# VoiceRAG AI

> A production-grade, voice-enabled Retrieval-Augmented Generation (RAG) system.

Upload your documents, ask questions by voice or text, and receive AI-generated spoken answers grounded in your content.

---

## Tech Stack

| Layer       | Technology                                         |
|-------------|---------------------------------------------------|
| Frontend    | Next.js 15, React 19, TypeScript, Tailwind, shadcn/ui |
| Backend     | Python 3.12, FastAPI, LangChain, Pydantic          |
| LLM         | Gemini API (generation + embeddings)               |
| Vector DB   | ChromaDB                                           |
| Database    | PostgreSQL 16                                      |
| TTS         | Edge-TTS                                           |
| Infra       | Docker, Docker Compose                             |
| Package Mgr | uv (Python), npm (Node)                            |

---

## Project Structure

```
VoiceRAG-AI/
├── frontend/       # Next.js 15 application
├── backend/        # FastAPI application
├── docs/
│   ├── architecture.md
│   └── roadmap.md
├── prompts/
│   ├── 00-master-prompt.md
│   ├── 01-rules.md
│   ├── phase-01.md
│   ├── phase-02.md
│   ├── phase-03.md
│   └── review.md
└── README.md
```

---

## Architecture

This project follows **Clean Architecture** with strict layer separation:

```
API Routes → Services → Repositories → DB / Vector Store
```

- No business logic in routes
- Dependency injection via FastAPI `Depends()`
- Full type coverage (Pydantic + TypeScript strict)
- SOLID principles throughout

See [`docs/architecture.md`](docs/architecture.md) for the full system design.

---

## Implementation Phases

See [`docs/roadmap.md`](docs/roadmap.md) for the 12-phase implementation plan.

| Phase | Title                  |
|-------|------------------------|
| 01    | Project Scaffolding    |
| 02    | Backend Foundation     |
| 03    | Document Ingestion     |
| 04    | RAG Pipeline           |
| 05    | Voice Layer            |
| 06    | Frontend Foundation    |
| 07    | Document UI            |
| 08    | Chat UI                |
| 09    | Voice UI               |
| 10    | Integration & Polish   |
| 11    | Testing                |
| 12    | Production Hardening   |

---

## Prerequisites

- Docker & Docker Compose
- Node.js 20+
- Python 3.12+
- uv (`pip install uv`)
- Gemini API key

---

## Quick Start

> ⚠️ Setup instructions will be completed after Phase 12.

---

## Environment Variables

Copy the example files and fill in your values:

```bash
cp backend/.env.example backend/.env
cp frontend/.env.local.example frontend/.env.local
```

---

## License

MIT
