# Phase 03 — Document Ingestion Pipeline

## Goal

Users can upload PDF documents. The system extracts text, chunks it, generates embeddings via Gemini, stores vectors in ChromaDB, and persists metadata in PostgreSQL.

---

## Deliverables

### `app/models/document.py` (Pydantic schemas)
```python
DocumentCreate    # internal: file bytes + filename
DocumentResponse  # API: id, name, status, page_count, created_at
DocumentStatus    # Enum: PROCESSING | READY | FAILED
ChunkMetadata     # doc_id, chunk_index, page_number, text
```

### `app/db/repositories/document_repo.py`
- `DocumentRepository(session: AsyncSession)`
- Methods: `create()`, `get_by_id()`, `list_all()`, `update_status()`, `delete()`
- Works only with the `Document` ORM model

### `app/utils/file_utils.py`
- `extract_text_from_pdf(file_bytes: bytes) -> list[PageContent]`
  - Uses PyMuPDF (`fitz`)
  - Returns page number + raw text per page
- `validate_pdf(file_bytes: bytes) -> bool`

### `app/utils/text_utils.py`
- `chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]`
  - Fixed-size chunking with overlap
- `clean_text(text: str) -> str`
  - Removes excess whitespace, control characters

### `app/services/embedding_service.py`
- `EmbeddingService(settings: Settings)`
- `async embed_texts(texts: list[str]) -> list[list[float]]`
  - Calls Gemini embedding API via `langchain-google-genai`
  - Batches requests to respect rate limits

### `app/vector_store/chroma_client.py`
- `get_chroma_client(settings: Settings) -> chromadb.AsyncClient`
- Returns configured async ChromaDB client (singleton)

### `app/vector_store/vector_repo.py`
- `VectorRepository(client: chromadb.AsyncClient, collection_name: str)`
- `async upsert(ids, embeddings, documents, metadatas)`
- `async query(embedding, n_results, where_filter) -> list[ChunkResult]`
- `async delete_by_document_id(doc_id: str)`

### `app/services/document_service.py`
- `DocumentService(doc_repo, vector_repo, embedding_service)`
- `async ingest(file_bytes, filename) -> DocumentResponse`
  1. Validate PDF
  2. Save metadata record (status=PROCESSING)
  3. Extract text via PyMuPDF
  4. Chunk text
  5. Generate embeddings
  6. Store in ChromaDB with metadata `{doc_id, chunk_index, page_number}`
  7. Update status=READY
  8. Return `DocumentResponse`
- `async list_documents() -> list[DocumentResponse]`
- `async delete_document(doc_id: str) -> None`

### `app/api/v1/documents.py`
```
POST   /api/v1/documents          # Upload PDF
GET    /api/v1/documents          # List all
DELETE /api/v1/documents/{doc_id} # Delete doc + vectors
```
- Accepts `multipart/form-data`
- No logic — delegates entirely to `DocumentService`

### Alembic Migration
- Migration for `documents` table:
  - `id` (UUID), `filename`, `status`, `page_count`, `chunk_count`, `created_at`, `updated_at`

---

## Success Criteria

- [ ] `POST /api/v1/documents` with a valid PDF returns `DocumentResponse` with `status=READY`
- [ ] Vectors are stored in ChromaDB and queryable
- [ ] Metadata persists in PostgreSQL `documents` table
- [ ] `GET /api/v1/documents` lists all uploaded documents
- [ ] `DELETE /api/v1/documents/{id}` removes from both stores
- [ ] Uploading a non-PDF returns `400` with a clear error message
