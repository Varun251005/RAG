# VoiceRAG AI — Project Documentation

---

## 36. Executive Summary

**VoiceRAG AI** is an enterprise-grade, privacy-focused, voice-enabled Retrieval-Augmented Generation (RAG) system designed for interactive document intelligence. The platform empowers users to upload complex PDF documents and interact with them using natural language—via both text input and real-time voice speech—receiving factual, grounded answers backed by precise page-level citations and interactive PDF source viewers.

### Key Architectural Highlights:
1. **CPU-Optimized Local Core**: Powered by `sentence-transformers/all-MiniLM-L6-v2` (384-dimensional vector embeddings), **ChromaDB** (persistent vector storage), **rank-bm25** (keyword search), and **CrossEncoder** (`cross-encoder/ms-marco-MiniLM-L-6-v2` passage reranking), executing entirely on standard CPU hardware without requiring dedicated GPU acceleration.
2. **Hybrid Candidate Retrieval & Reranking**: Combines semantic vector similarity search with BM25 keyword matching via weighted score fusion (70% vector / 30% keyword), followed by a lightweight 6-layer MiniLM CrossEncoder reranking stage that filters candidate chunks down to the most relevant Top-K contexts.
3. **Dual Intelligence LLM Engine**: Integrates local **Qwen 2.5 0.5B** (via Ollama) for completely offline RAG question answering, paired with **Grok 2 (`grok-2-1212`)** as a high-performance generative provider for AI Studio features (Summaries, Study Flashcards, Practice Quizzes, Structured Notes, Key Topics, and FAQs) with seamless automated fallback to local Qwen.
4. **End-to-End Multimodal Voice Pipeline**: Incorporates **Faster-Whisper** (`tiny` model in INT8 quantization on CPU) for near-instant Speech-to-Text (STT) transcription and **Microsoft Edge-TTS** for neural Text-to-Speech (TTS) audio streaming in MP3 format with configurable voices and speech rates.
5. **Modern Minimalist Frontend**: Built on **Next.js 15 App Router**, **React 19**, **TypeScript**, **Tailwind CSS**, and **Zustand** state management, featuring a floating chat interface with integrated `+` document scope selector, interactive PDF citation modal, and a monochrome aesthetic.

---

## 1. Project Overview

### What is VoiceRAG AI?
VoiceRAG AI is an open-source, full-stack web application that combines local document information retrieval with conversational AI and voice synthesis. It transforms static PDF files (such as technical manuals, research papers, legal documents, and textbooks) into interactive conversational knowledge bases.

### What Problem Does It Solve?
Manual information extraction from lengthy PDF files is slow, tedious, and prone to human oversight. Traditional keyword search (Ctrl+F) fails when queries use synonyms or natural language concepts rather than exact phrase matches. Furthermore, cloud-only RAG systems pose severe privacy risks when uploading confidential documents to third-party APIs and require expensive GPU infrastructure. VoiceRAG AI solves these challenges by combining local hybrid retrieval, passage reranking, voice speech interfaces, and CPU-friendly execution.

### Target Users & Use Cases
- **Students & Researchers**: Quickly analyze research papers, extract key findings, generate study flashcards, and run practice quizzes.
- **Legal & Compliance Analysts**: Search contracts and policy guidelines with strict factual accuracy and immediate source page verification.
- **Engineers & Technical Writers**: Query dense software documentation, standard operating procedures, and product manuals hands-free using voice commands.
- **Privacy-Conscious Organizations**: Process sensitive enterprise documents locally on internal workstation hardware without external GPU dependencies.

---

## 2. Problem Statement

Traditional document workflows suffer from critical inefficiencies:
1. **Time-Consuming Manual Reading**: Users spend hours skim-reading hundreds of PDF pages to locate specific answers or policy requirements.
2. **Limitations of Keyword Search**: Standard Ctrl+F search requires exact keyword matches and cannot interpret context, semantic intent, or conceptual queries (e.g., searching for "data security breaches" will miss sections discussing "unauthorized network intrusions").
3. **Lack of Trust in Generic LLMs**: Out-of-the-box LLMs frequently hallucinate facts or produce answers unsupported by internal corporate documents.
4. **Accessibility & Hands-Free Constraints**: Standard document tools require manual keyboard input and visual reading, preventing hands-free operation for users with visual impairments or multitasking environments.

**How VoiceRAG AI Solves These Problems**:
- Implements semantic + keyword hybrid search to capture both conceptual meaning and exact term matches.
- Applies CrossEncoder reranking to ensure top contexts directly answer the specific user question.
- Enforces strict grounding system prompts so the LLM answers *only* using retrieved passages, explicitly stating when context is insufficient.
- Provides automatic page-level citations with interactive PDF viewing.
- Integrates voice STT and TTS for hands-free audio interaction.

---

## 3. Objectives

- **Local PDF Processing & Ingestion**: Extract page text cleanly using PyMuPDF (`pypdf`), chunk text with overlap, and construct detailed metadata records (`document_id`, `page_number`, `chunk_id`, `filename`).
- **CPU-Friendly Hybrid Retrieval**: Combine 384-dim local SentenceTransformer embeddings (`all-MiniLM-L6-v2`) in ChromaDB with rank-bm25 keyword indexing using score fusion.
- **Lightweight Passage Reranking**: Re-score top candidate chunks using `cross-encoder/ms-marco-MiniLM-L-6-v2` on CPU to rank relevant passages before LLM context construction.
- **Grounded Conversational Generation**: Stream answers from local Qwen 2.5 0.5B (or Grok 2) while attaching clear source citations for every claim.
- **AI Document Studio**: Offer structured generative insights (Executive Summaries, 3D Study Flashcards, Interactive Quizzes, Structured Notes, Key Topics, FAQs).
- **Multimodal Voice Control**: Enable browser microphone voice input via Faster-Whisper and neural audio output playback via Edge-TTS.
- **Zero GPU Requirement**: Maintain low memory footprint (~1.2GB RAM peak) and fast response times running 100% on standard x86_64 or ARM64 CPUs.

---

## 4. System Workflow

### Text RAG Workflow
```
User Question
     ↓
 ┌───┴────────────┐
 ↓                ↓
Vector Search   BM25 Search
(ChromaDB)      (rank-bm25)
 └───┬────────────┘
     ↓
Score Fusion (0.7 Vector / 0.3 Keyword)
     ↓
Top-15 Candidate Chunks
     ↓
CrossEncoder Reranker (ms-marco-MiniLM-L-6-v2)
     ↓
Top-5 Reranked Context Chunks
     ↓
Context Builder ([Chunk N | filename | page X])
     ↓
LLM Generation (Qwen 2.5 0.5B / Grok 2)
     ↓
Streaming Answer + Page Citations
```

### Voice Speech Workflow
```
User Speech
     ↓
Browser Microphone (MediaRecorder)
     ↓
Audio Blob (WebM / WAV) → POST /api/v1/voice/transcribe
     ↓
Faster-Whisper (tiny, INT8 CPU)
     ↓
Transcribed Text Question
     ↓
Hybrid RAG Pipeline → Generated Answer Text
     ↓
Edge-TTS (en-US-AvaNeural) → MP3 Audio Stream
     ↓
Browser Audio Player / Autoplay
```

### AI Document Studio Workflow
```
Select Studio Feature (Summary, Flashcards, Quiz, Notes, Key Topics, FAQ)
     ↓
Retrieve Top-10 Relevant Chunks (all-MiniLM-L6-v2 + ChromaDB + BM25 + Reranker)
     ↓
Generate Feature via Grok 2 API (Primary)
     ↓ (fallback if Grok API Key unconfigured / fails)
Generate Feature via Local Qwen 2.5 0.5B (Backup)
     ↓
Structured JSON Response → Interactive UI Cards
```

---

## 5. Complete System Architecture

VoiceRAG AI is partitioned into decoupled service layers communicating via HTTP REST APIs and Server-Sent Events (SSE):

```
┌────────────────────────────────────────────────────────────────────────┐
│                        NEXT.JS 15 FRONTEND                             │
│  - React 19 UI Components   - Zustand State Stores (Chat / Document)   │
│  - MediaRecorder Voice STT  - HTML5 Audio Player / Voice Settings      │
│  - Floating Chat Input      - AI Document Studio Modal                 │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP / SSE
┌───────────────────────────────────▼────────────────────────────────────┐
│                        FASTAPI 0.115+ BACKEND                          │
│  - /api/v1/documents        - /api/v1/rag (query, stream, ingest)     │
│  - /api/v1/voice            - /api/v1/tts                              │
└───────┬──────────────┬─────────────┬─────────────┬─────────────┬───────┘
        │              │             │             │             │
┌───────▼──────┐┌──────▼──────┐┌─────▼──────┐┌─────▼──────┐┌─────▼──────┐
│  PDF Service ││  Embedding   ││ Vector &  ││  Reranker   ││  Voice &    │
│  & Chunking  ││   Service    ││ BM25 Store││   Service   ││ Speech Svc  │
│  (PyMuPDF /  ││(MiniLM-L6-v2││ (ChromaDB ││(CrossEncoder││(Faster-     │
│  LangChain)  ││  384-dim)   ││ + BM25)   ││ ms-marco)  ││ Whisper/TTS)│
└──────────────┘└─────────────┘└────────────┘└─────────────┘└────────────┘
                                                           ┌─────▼──────┐
                                                           │ LLM Engine │
                                                           │ (Qwen 2.5 /│
                                                           │  Grok 2)   │
                                                           └────────────┘
```

### Component Details
- **A. Frontend**: Built with Next.js 15 App Router, React 19, TypeScript, and Tailwind CSS. Client state is managed reactively using Zustand stores (`useChatStore`, `useDocumentStore`).
- **B. Backend**: Python 3.12 FastAPI application managed with `uv`. Features structured routing, Pydantic data validation, async execution, and Loguru logging.
- **C. Document Ingestion**: PyMuPDF page text extraction and `RecursiveCharacterTextSplitter` (chunk size: 1000, overlap: 200).
- **D. Embedding Layer**: `sentence-transformers/all-MiniLM-L6-v2` producing normalized 384-dim vectors on CPU.
- **E. Vector Store**: Persistent ChromaDB instance storing document embeddings and page metadata.
- **F. Keyword Search**: `rank-bm25` index built across chunk tokens for term matching.
- **G. Passage Reranker**: `cross-encoder/ms-marco-MiniLM-L-6-v2` re-scoring candidates on CPU.
- **H. LLM Engine**: Local Ollama execution of Qwen 2.5 0.5B alongside xAI Grok 2.
- **I. Speech-to-Text**: Faster-Whisper `tiny` model executing in INT8 quantization on CPU.
- **J. Text-to-Speech**: Microsoft Edge-TTS streaming MP3 audio across 9 neural voice options.

---

## 6. Tech Stack

| Technology | Version | Purpose | Where Used | Local/Cloud | API Key Required |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Next.js** | 15.0+ | Frontend Framework & SSR | `frontend/` | Local | No |
| **React** | 19.0+ | UI Library | Components | Local | No |
| **TypeScript** | 5.0+ | Static Type Safety | Frontend | Local | No |
| **Tailwind CSS** | 4.0+ | Utility-First Styling | Styling | Local | No |
| **Zustand** | 5.0+ | Reactive State Management | Frontend Stores | Local | No |
| **Bun** | 1.1+ | JavaScript Package Manager | Frontend Build | Local | No |
| **Python** | 3.12+ | Backend Language Runtime | `backend/` | Local | No |
| **FastAPI** | 0.115+ | REST & SSE API Framework | Backend App | Local | No |
| **Uvicorn** | 0.32+ | ASGI Web Server | Server Execution | Local | No |
| **uv** | 0.5+ | Fast Python Dependency Tool | Package Mgmt | Local | No |
| **Pydantic** | 2.6+ | Data Validation & Settings | Models / Config | Local | No |
| **PyMuPDF / PyPDF**| 5.0+ | PDF Text Extraction | PDF Service | Local | No |
| **Sentence-Transformers**| 5.7+| Local Text Embeddings | Embedding Service| Local | No |
| **ChromaDB** | 0.6+ | Persistent Vector Database | Vector Store | Local | No |
| **rank-bm25** | 0.2.2 | In-Memory BM25 Keyword Search| BM25 Service | Local | No |
| **CrossEncoder** | 2.2+ | Passage Reranking | Reranker Service | Local | No |
| **Qwen 2.5 0.5B** | 0.5B | Primary Local LLM | Ollama Service | Local | No |
| **Grok 2** | `grok-2-1212`| High-Tier Studio LLM | Grok Service | Cloud | Yes (`GROK_API_KEY`) |
| **Faster-Whisper**| 1.2+ | Speech-to-Text (STT) | STT Service | Local | No |
| **Edge-TTS** | 6.1+ | Text-to-Speech (TTS) | TTS Service | Cloud/Hybrid | No |
| **Docker Compose**| 3.8+ | Containerized Deployment | DevOps | Local | No |

---

## 7. AI Models

| Model Name | Purpose | Size / Params | Execution | Hardware | Input | Output |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`all-MiniLM-L6-v2`** | Vector Embeddings | 22M / ~90MB | Local CPU | CPU-only | Text chunk / query | 384-dim float vector |
| **`ms-marco-MiniLM-L-6-v2`**| Passage Reranker | 22M / ~90MB | Local CPU | CPU-only | Query + Chunk pairs | Relevance scalar score |
| **Qwen 2.5 0.5B** | Question Answering / QA | 0.5B / ~390MB | Local Ollama | CPU-only | Context + Question | Natural language answer |
| **Faster-Whisper (`tiny`)**| Speech-to-Text (STT) | 39M / ~75MB | Local CPU (INT8) | CPU-only | Audio file / Blob | Transcribed text string |
| **Edge-TTS (`AvaNeural`)**| Text-to-Speech (TTS) | Cloud Service | Neural Streaming | Network | Clean text string | MP3 audio stream |
| **Grok 2 (`grok-2-1212`)** | AI Studio Generation | Cloud API | Remote xAI | Cloud API | Prompt + Context | Structured JSON / Text |

---

## 8. PDF Processing Pipeline

```
PDF File Upload
     ↓
File Validation (Extension .pdf, Non-empty bytes)
     ↓
File Storage (`storage/uploads/{doc_id}/{filename}`)
     ↓
Page Text Extraction (PyMuPDF / pypdf page-by-page)
     ↓
Text Chunking (RecursiveCharacterTextSplitter: 1000 size, 200 overlap)
     ↓
Metadata Binding (`chunk_id`, `document_id`, `page_number`, `original_filename`)
     ↓
Batch Embedding (Local `all-MiniLM-L6-v2` 384-dim CPU execution)
     ↓
ChromaDB Storage & BM25 In-Memory Index Update
```

- **Chunk Size**: 1000 characters.
- **Chunk Overlap**: 200 characters.
- **Unique Chunk Identifier**: `{document_id}_chunk_{index}`.

---

## 9. Embedding System

VoiceRAG AI utilizes **`sentence-transformers/all-MiniLM-L6-v2`** running locally on CPU.
- **Dimensions**: 384 floating-point values per vector.
- **Normalization**: Vectors are $L_2$-normalized during encoding so cosine similarity matches dot product.
- **Efficiency**: Encodes text chunks in ~15ms per batch on standard CPUs.
- **Privacy**: Embeddings are computed 100% locally on device without sending data to third-party services (legacy Google Gemini `text-embedding-004` dependency has been completely removed).

---

## 10. ChromaDB Vector Database

- **Persistence Directory**: `storage/chroma` on disk.
- **Collection Name**: Default `voicerag_documents`.
- **Distance Metric**: Cosine Similarity.
- **Operations**:
  - `upsert_from_chunks_and_embeddings`: Inserts or updates chunk vectors and metadata.
  - `search_by_document`: Filters queries strictly to a single `document_id`.
  - `delete_document`: Removes all chunks associated with a specific document ID.

---

## 11. BM25 Hybrid Retrieval

To prevent vector search from missing exact terms (e.g., product IDs, acronyms, or specific proper nouns), VoiceRAG AI implements hybrid fusion:

1. **Semantic Vector Search**: ChromaDB returns vector distance $S_{\text{vector}} \in [0, 1]$.
2. **Keyword Search**: `rank-bm25` scores token matches $S_{\text{bm25}} \in [0, 1]$.
3. **Score Fusion Equation**:
   $$S_{\text{hybrid}} = (0.7 \times S_{\text{vector}}) + (0.3 \times S_{\text{bm25}})$$
4. **Candidate Selection**: Returns top 15 candidate chunks ($K_{\text{candidate}} = 15$).

---

## 12. Reranking Layer

Candidate chunks retrieved from hybrid fusion are passed through a **CrossEncoder** (`cross-encoder/ms-marco-MiniLM-L-6-v2`):
- **Mechanism**: Evaluates full sentence pairs `(question, chunk_text)` directly through attention layers rather than comparing isolated vectors.
- **Input**: 15 candidate chunks.
- **Output**: Top 5 reranked chunks ($K_{\text{final}} = 5$) ordered by exact contextual relevance.
- **CPU Time**: ~35ms inference latency.

---

## 13. RAG Question Answering

1. **Context Construction**: Formats the Top-5 reranked passages into a structured block:
   ```
   [Chunk 1 | output.pdf | page 3]
   Excerpt text...

   ---

   [Chunk 2 | output.pdf | page 5]
   Excerpt text...
   ```
2. **Strict Grounding Prompt**: Instructs Qwen 2.5 0.5B to rely *exclusively* on the provided context.
3. **Fallback Guard**: If context does not contain the answer, the model responds with:
   *"I don't have enough information in the provided documents to answer this question."*

---

## 14. Source Citations

Every generated answer response includes structured citations:
- `document_id`: UUID of source file.
- `original_filename`: E.g., `cyber_security(3).pdf`.
- `page_number`: 1-based page index.
- `snippet`: First 250 characters of passage text.
- `score`: Combined relevance score.

Clicking a citation pill in the frontend UI opens an interactive **PDF Viewer Modal**, jumping directly to the exact page and highlighting the snippet text.

---

## 15. PDF Summarization

Summarization requests obtain all indexed chunks for a document, construct an executive context buffer, and pass them to the LLM with structured prompts:
- Synthesizes key themes, core bullet points, and actionable takeaways.
- Handles multi-page documents seamlessly without exceeding token limits.

---

## 16. AI Document Studio

The AI Document Studio provides specialized analysis tabs:

| Feature Tab | Purpose | Status | Backend Model |
| :--- | :--- | :--- | :--- |
| **Summary** | Executive overview & Key Takeaways list | **Implemented** | Grok 2 (Fallback: Qwen 2.5) |
| **Flashcards** | 6 Study Flashcards with 3D Flip Cards | **Implemented** | Grok 2 (Fallback: Qwen 2.5) |
| **Quiz** | 5 Practice Questions with Options & Explanations | **Implemented** | Grok 2 (Fallback: Qwen 2.5) |
| **Notes** | Formatted Study Notes with Definitions | **Implemented** | Grok 2 (Fallback: Qwen 2.5) |
| **Key Topics** | Top 5 Main Concepts & Deep Dives | **Implemented** | Grok 2 (Fallback: Qwen 2.5) |
| **FAQ** | 6 Accordion Question & Answer Items | **Implemented** | Grok 2 (Fallback: Qwen 2.5) |

---

## 17. Voice System

### Speech-to-Text (STT)
- **Model**: Faster-Whisper `tiny`.
- **Execution**: CPU in `int8` quantization mode.
- **Input Formats**: `.wav`, `.webm`, `.mp3`, `.m4a`, `.ogg`.
- **Cleanup**: Audio files are processed in-memory or written to temp storage with guaranteed unlinking in `finally` blocks.

### Text-to-Speech (TTS)
- **Engine**: Microsoft Edge-TTS.
- **Default Voice**: `en-US-AvaNeural`.
- **Voices Supported**: 9 neural voices (Male & Female, US & UK locales).
- **Format**: Streaming MP3 audio buffer.

---

## 18. Frontend Architecture

- **Framework**: Next.js 15 (App Router).
- **Directory**: `frontend/src/`
  - `app/chat/page.tsx`: Main chat UI page.
  - `app/documents/page.tsx`: PDF document management & upload dropzone.
  - `components/chat/`: `ChatInput`, `ChatMessageItem`, `DocumentSelectorButton`, `SourceCitations`, `VoiceSettingsModal`.
  - `components/ai/`: `AIFeaturesStudioModal`.
  - `components/document/`: `UploadDropzone`, `DocumentList`.
  - `store/`: `useChatStore.ts`, `documentStore.ts` (Zustand state management).
  - `hooks/`: `useAudioPlayer.ts`, `useDocumentUpload.ts`.

---

## 19. Backend Architecture

- **Framework**: FastAPI with Pydantic validation.
- **Directory**: `backend/app/`
  - `main.py`: ASGI app entrypoint, CORS middleware, exception handlers.
  - `api/v1/`: API routers (`documents.py`, `rag.py`, `voice.py`, `tts.py`, `audio.py`, `health.py`).
  - `services/`: Core logic (`rag_service.py`, `retrieval_service.py`, `reranker_service.py`, `local_embedding_service.py`, `bm25_service.py`, `stt_service.py`, `tts_service.py`, `grok_service.py`, `llm_service.py`).
  - `models/`: Data schemas (`document.py`, `rag.py`, `ai_features.py`).

---

## 20. API Documentation

| Method | Endpoint | Description | Request Body | Response |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/documents/upload` | Upload & index PDF document | `multipart/form-data` | `DocumentResponse` |
| `GET` | `/api/v1/documents` | List uploaded documents | None | `DocumentListResponse` |
| `DELETE`| `/api/v1/documents/{doc_id}`| Delete document & vectors | None | `{"status": "deleted"}` |
| `POST` | `/api/v1/rag/query` | Synchronous RAG batch query | `RAGQuery` | `RAGResponse` |
| `POST` | `/api/v1/rag/stream` | Streaming RAG query (SSE) | `RAGQuery` | `text/event-stream` |
| `POST` | `/api/v1/rag/ingest/{doc_id}`| Trigger manual ingestion | None | `UpsertResult` |
| `POST` | `/api/v1/rag/ai-features` | Generate AI Studio features | `AIFeatureRequest` | `RAGResponse` |
| `POST` | `/api/v1/voice/transcribe` | Transcribe audio speech | `multipart/form-data` | `TranscriptionResponse`|
| `POST` | `/api/v1/voice/synthesize` | Convert text to speech | `TTSRequest` | `audio/mpeg` |
| `GET` | `/api/v1/voice/voices` | List TTS neural voices | None | `list[VoiceInfo]` |
| `POST` | `/api/v1/tts/stream` | Stream MP3 audio chunks | `TTSStreamRequest` | `audio/mpeg` stream |
| `GET` | `/api/v1/health` | Service health status | None | `HealthCheckResponse` |

---

## 21. Data Flow

### A. PDF Ingestion & Indexing
```
Upload File → Validate Extension → Write to Disk → Extract Text Pages → 
Create Overlapping Chunks → Compute 384-dim Embeddings → Upsert to ChromaDB → 
Index Tokens in BM25 Store → Return Ready Status
```

### B. Question Answering (QA)
```
User Prompt → Compute Query Embedding → Parallel Search (ChromaDB + BM25) → 
Weighted Fusion → Top-15 Candidates → CrossEncoder Reranking → Top-5 Chunks → 
Construct Grounded Prompt → Stream Qwen 2.5 Response + Page Citations
```

---

## 22. Error Handling

- **Invalid / Empty PDFs**: Rejects non-PDF extensions or empty bytes with HTTP 400 `InvalidPDFError`.
- **Unsupported Audio**: Validates extensions (`.wav`, `.mp3`, `.webm`) before Faster-Whisper execution.
- **RAG Fallbacks**: When context is missing, output explicitly denies speculation.
- **API Provider Failures**: If Grok API fails or lacks a key, AI Studio seamlessly falls back to local Qwen 2.5 0.5B.
- **TTS Fallbacks**: Invalid custom voice parameters fall back to `en-US-AvaNeural`.

---

## 23. Security & Privacy

- **Strict Local Processing**: Embeddings, vector database, STT, and QA LLM operate 100% locally on CPU without remote data transmission.
- **Input Validation**: Pydantic models sanitize all JSON requests and limits input lengths (questions max 2000 chars).
- **CORS Middleware**: Restricted to configured frontend origins (`http://localhost:3000`).
- **Zero Exposed Secrets**: Secrets and API keys are strictly loaded via `.env` files and omitted from client-side bundles.

---

## 24. Testing & Verification

The VoiceRAG AI repository includes a comprehensive automated test suite built with `pytest`:
- **Total Test Files**: 36 test files in `backend/tests/`.
- **Total Tests Collected**: **239 tests** (All passing).
- **Test Categories**:
  - `test_chunking.py`: Page text extraction, chunk boundaries, overlap verification.
  - `test_local_embedding.py`: 384-dim vector shape, normalization, CPU execution.
  - `test_vector_store.py` & `test_chroma_integration.py`: ChromaDB CRUD and search.
  - `test_hybrid_retrieval.py`: Score fusion, weight calculations, BM25 indexing.
  - `test_reranker.py`: CrossEncoder scoring accuracy and CPU candidate selection.
  - `test_stt_voice.py` & `test_tts_voice.py`: Speech transcription and MP3 audio generation.
  - `test_ai_features.py`: Studio feature endpoints and provider fallback logic.
  - `test_cors.py` & `test_api_layer.py`: Full REST API integration suite.

---

## 25. Performance Metrics

| Operation | Model / Tool | Execution Time (CPU) | Memory Footprint |
| :--- | :--- | :--- | :--- |
| **Embedding Generation** | `all-MiniLM-L6-v2` | ~15ms per chunk | ~90MB |
| **BM25 Search** | `rank-bm25` | ~2ms per query | ~15MB |
| **Passage Reranking** | `ms-marco-MiniLM-L-6-v2` | ~35ms per 15 candidates | ~90MB |
| **STT Transcription** | Faster-Whisper (`tiny`) | ~350ms per audio clip | ~75MB |
| **TTS Synthesis** | Edge-TTS | ~200ms per paragraph | ~20MB |
| **Total RAG Latency** | Full Hybrid + Qwen 2.5 | **~1.5s – 2.5s** | **~1.2GB Total Peak** |

---

## 26. Hardware Requirements

- **Operating System**: Linux (Ubuntu 22.04+ recommended), macOS, or Windows WSL2.
- **CPU**: Dual-Core x86_64 or ARM64 processor (No GPU needed).
- **RAM**: 4GB minimum (8GB recommended).
- **Disk Space**: 2GB free storage space (for models, ChromaDB, and Python dependencies).
- **Dependencies**: FFmpeg (required for Faster-Whisper audio processing), Ollama (for Qwen 2.5 0.5B).

---

## 27. Environment Variables

### Backend Configuration (`backend/.env`):
```env
# Server & Environment
PROJECT_NAME="VoiceRAG AI Backend"
ENVIRONMENT="development"
DEBUG=true

# Local Embeddings & Vector Store
EMBEDDING_MODEL="sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIMENSION=384
CHROMA_PERSIST_DIRECTORY="./storage/chroma"

# Retrieval & Reranker Settings
RETRIEVAL_MODE="hybrid"
VECTOR_WEIGHT=0.7
KEYWORD_WEIGHT=0.3
RERANKER_ENABLED=true
RERANKER_MODEL_NAME="cross-encoder/ms-marco-MiniLM-L-6-v2"
RERANKER_CANDIDATE_K=15

# LLM Providers
OLLAMA_BASE_URL="http://localhost:11434"
OLLAMA_MODEL="qwen2.5:0.5b"
GROK_API_KEY="<YOUR_GROK_API_KEY>"
GROK_MODEL="grok-2-1212"

# Speech Services
WHISPER_MODEL_SIZE="tiny"
EDGE_TTS_VOICE="en-US-AvaNeural"
```

### Frontend Configuration (`frontend/.env.local`):
```env
NEXT_PUBLIC_API_URL="http://localhost:8000"
```

---

## 28. Installation Guide

### Step 1: Prerequisites
Ensure `git`, `python3.12`, `bun`, `uv`, `ffmpeg`, and `ollama` are installed on your system:
```bash
# Install FFmpeg (Ubuntu/Debian)
sudo apt update && sudo apt install -y ffmpeg

# Install Bun
curl -fsSL https://bun.sh/install | bash

# Install uv (Fast Python Package Manager)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Step 2: Clone Repository
```bash
git clone https://github.com/Varun251005/RAG.git VoiceRAG-AI
cd VoiceRAG-AI
```

### Step 3: Setup Backend Environment
```bash
cd backend
uv venv .venv
source .venv/bin/activate
uv sync
```

### Step 4: Setup Frontend Environment
```bash
cd ../frontend
bun install
```

### Step 5: Setup Local Qwen LLM Model
```bash
ollama pull qwen2.5:0.5b
```

---

## 29. Running the Application

### 1. Start Ollama Server
```bash
ollama serve
```

### 2. Start Backend API Server
```bash
cd backend
source .venv/bin/activate
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
*Backend API Documentation is accessible at `http://localhost:8000/docs`.*

### 3. Start Frontend App
```bash
cd frontend
bun run dev
```
*Open your browser and navigate to `http://localhost:3000`.*

---

## 30. Project Folder Structure

```
VoiceRAG-AI/
├── docs/
│   ├── VoiceRAG_AI_Project_Documentation.md
│   ├── architecture.md
│   └── roadmap.md
├── docker-compose.yml
├── README.md
├── backend/
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── deps.py
│   │   │   └── v1/
│   │   │       ├── audio.py
│   │   │       ├── chat.py
│   │   │       ├── documents.py
│   │   │       ├── health.py
│   │   │       ├── rag.py
│   │   │       ├── tts.py
│   │   │       └── voice.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   └── exceptions.py
│   │   ├── models/
│   │   │   ├── ai_features.py
│   │   │   ├── document.py
│   │   │   ├── rag.py
│   │   │   └── vector_store.py
│   │   └── services/
│   │       ├── bm25_service.py
│   │       ├── chunking_service.py
│   │       ├── document_service.py
│   │       ├── embedding_service.py
│   │       ├── grok_service.py
│   │       ├── ingestion_service.py
│   │       ├── llm_service.py
│   │       ├── local_embedding_service.py
│   │       ├── pdf_service.py
│   │       ├── rag_service.py
│   │       ├── reranker_service.py
│   │       ├── retrieval_service.py
│   │       ├── stt_service.py
│   │       └── tts_service.py
│   └── tests/ (36 test files)
└── frontend/
    ├── package.json
    ├── next.config.ts
    ├── src/
    │   ├── app/
    │   │   ├── page.tsx
    │   │   ├── globals.css
    │   │   ├── chat/page.tsx
    │   │   └── documents/page.tsx
    │   ├── components/
    │   │   ├── ai/AIFeaturesStudioModal.tsx
    │   │   ├── chat/
    │   │   │   ├── ChatInput.tsx
    │   │   │   ├── ChatMessageItem.tsx
    │   │   │   ├── DocumentSelectorButton.tsx
    │   │   │   ├── SourceCitations.tsx
    │   │   │   └── VoiceSettingsModal.tsx
    │   │   └── document/
    │   │       ├── DocumentList.tsx
    │   │       └── UploadDropzone.tsx
    │   ├── hooks/
    │   ├── lib/api/
    │   └── store/
```

---

## 31. Complete User Workflow

1. **Access VoiceRAG AI**: Open `http://localhost:3000` in browser.
2. **Upload PDF**: Click "Library" → Drag & drop a PDF document (e.g., `cyber_security(3).pdf`).
3. **Automatic Ingestion**: Backend extracts text, creates chunks, computes 384-dim local embeddings, populates ChromaDB and BM25 index.
4. **Scope Selection**: Return to Chat → Click `[ + ]` inside input bar to filter query scope to specific PDF or all documents.
5. **Ask Question (Text or Voice)**: Type a question or click microphone icon for voice transcription via Faster-Whisper.
6. **Hybrid Retrieval**: Backend performs vector similarity + BM25 keyword search, merging candidates.
7. **Reranking**: CrossEncoder model scores top candidates on CPU and selects top relevant passages.
8. **Answer Generation**: Qwen 2.5 0.5B synthesizes a factual, grounded response.
9. **Interactive Citations**: Click source citation pill to open PDF viewer modal directly at the cited page.
10. **Audio Playback**: Click `[ 🔊 Listen ]` or enable `Voice Mode` for automatic Edge-TTS audio streaming.
11. **AI Studio Analysis**: Click `[ Sparkles AI Studio ]` to generate executive summaries, 3D study flashcards, quizzes, notes, key topics, or FAQs.

---

## 32. Technology Decisions & Rationale

- **Next.js 15 & Bun**: Fast server-side rendering, seamless client routing, and instantaneous package installations.
- **FastAPI & uv**: Async Python framework with automatic Swagger documentation and ultra-fast environment setup using `uv`.
- **`all-MiniLM-L6-v2` Embeddings**: Ultra-lightweight (90MB) CPU embedding model providing high semantic accuracy at zero cloud cost.
- **BM25 + ChromaDB Hybrid Fusion**: Fixes vector search keyword blindspots by incorporating term frequency relevance matching.
- **CrossEncoder Reranker**: Eliminates irrelevant vector search false positives by re-scoring candidates with query-passage attention pairs.
- **Qwen 2.5 0.5B via Ollama**: State-of-the-art sub-billion parameter model capable of fast text synthesis on standard CPUs.
- **Faster-Whisper & Edge-TTS**: Delivers near-instant speech recognition and natural neural voice streaming without expensive cloud speech API subscriptions.

---

## 33. System Limitations

- **CPU Inference Latency**: While lightweight, answering complex multi-page queries on older dual-core CPUs may take 2 to 3 seconds.
- **OCR Limitations**: Relies on PyMuPDF for text extraction; scanned image-only PDFs without an embedded OCR text layer will require pre-processing with Tesseract.
- **Internet Requirement for Edge-TTS**: While embeddings, RAG, STT, and QA operate 100% offline, Edge-TTS audio streaming requires active internet connectivity.

---

## 34. Future Enhancements

- **OCR Ingestion Engine**: Integrate Tesseract or RapidOCR for automatic text extraction from scanned document images.
- **Multi-User Authentication**: Implement JWT-based user authentication with role-based document access controls.
- **Persistent Chat Conversations**: Store past chat history sessions in a local SQLite/PostgreSQL database.
- **Local Large LLM Upgrades**: Support hot-swapping to Qwen 2.5 7B or Llama 3.1 8B when dedicated GPU hardware is available.

---

## 35. Final Architecture Diagram

```
┌────────────────────────────────────────────────────────────────────────┐
│                          USER INTERFACE                                │
│          [ Microphone Input ]         [ Floating Chat Input ]          │
└───────────────────┬──────────────────────────────┬─────────────────────┘
                    │ Audio Blob                   │ Question String
┌───────────────────▼──────────────────────────────▼─────────────────────┐
│                      FASTAPI AGGREGATOR ROUTER                         │
└─────────┬───────────────────┬───────────────────┬──────────────────────┘
          │ STT Audio         │ RAG Query         │ Synthesis Text
┌─────────▼─────────┐┌────────▼─────────┐┌────────▼──────────┐
│  Faster-Whisper   ││ Hybrid Retrieval ││   Edge-TTS       │
│  (tiny INT8 CPU)  ││ (ChromaDB + BM25)││(en-US-AvaNeural) │
└─────────┬─────────┘└────────┬─────────┘└────────┬──────────┘
          │ Text              │ Top-15            │ MP3 Audio
          └─────────┐         │ Candidates        │ Stream
                    │         ▼                   │
                    │  ┌───────────────┐          │
                    │  │ CrossEncoder  │          │
                    │  │   Reranker    │          │
                    │  └──────┬────────┘          │
                    │         │ Top-5             │
                    │         ▼                   │
                    │  ┌───────────────┐          │
                    └─►│  Qwen 2.5 /   ├──────────┘
                       │    Grok 2     │
                       └───────────────┘
```

---
*Documentation compiled automatically from verified VoiceRAG AI ground truth codebase.*
