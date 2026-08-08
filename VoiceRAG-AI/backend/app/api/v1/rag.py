"""
RAG API router — provides both batch and streaming query endpoints.

Routes
------
POST /rag/query
    Batch mode — waits for the full answer and returns ``RAGResponse``.

POST /rag/stream
    Streaming mode — returns a ``text/event-stream`` response with
    ``token``, ``sources``, ``done`` (and optionally ``error``) events.

POST /rag/ingest/{doc_id}
    Ingest pipeline — runs chunk → embed → store for an already-uploaded
    document.  Required before the document can be queried via RAG.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path
from fastapi.responses import StreamingResponse
from loguru import logger

from app.api.deps import (
    get_document_service,
    get_embedding_service,
    get_rag_service,
    get_vector_store_service,
)
from app.models.ai_features import AIFeatureRequest
from app.models.rag import RAGQuery, RAGResponse

from app.services.document_service import DocumentService
from app.services.embedding_service import EmbeddingService
from app.services.rag_service import RAGService
from app.services.vector_store_service import VectorStoreService
from app.models.vector_store import UpsertResult
from app.core.exceptions import NotFoundError
from app.services.chunking_service import ChunkingService

router = APIRouter()


# ---------------------------------------------------------------------------
# Batch query
# ---------------------------------------------------------------------------


@router.post(
    "/query",
    response_model=RAGResponse,
    summary="RAG batch query",
    description=(
        "Embed the question, retrieve the top-k most relevant document chunks "
        "from ChromaDB, and return a Gemini-generated answer together with "
        "source citations.  Waits for the full answer before responding."
    ),
    tags=["RAG"],
)
async def rag_query(
    query: RAGQuery,
    service: RAGService = Depends(get_rag_service),
) -> RAGResponse:
    logger.info(f"RAG batch | question_len={len(query.question)} | top_k={query.top_k}")
    return await service.query(
        question=query.question,
        collection=query.collection,
        top_k=query.top_k,
        document_id=query.document_id,
    )


# ---------------------------------------------------------------------------
# Streaming query
# ---------------------------------------------------------------------------


@router.post(
    "/stream",
    summary="RAG streaming query (SSE)",
    description=(
        "Streaming version of the RAG query endpoint. "
        "Returns a ``text/event-stream`` response. "
        "Events: ``token`` (answer tokens), ``sources`` (citations), ``done``, ``error``."
    ),
    tags=["RAG"],
    responses={
        200: {
            "content": {"text/event-stream": {}},
            "description": "Server-sent events stream.",
        }
    },
)
async def rag_stream(
    query: RAGQuery,
    service: RAGService = Depends(get_rag_service),
) -> StreamingResponse:
    logger.info(f"RAG stream | question_len={len(query.question)} | top_k={query.top_k}")

    async def event_generator():
        async for sse_line in service.stream_query(
            question=query.question,
            collection=query.collection,
            top_k=query.top_k,
            document_id=query.document_id,
        ):
            yield sse_line

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            # Prevent proxies / Nginx from buffering the SSE stream.
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Ingest pipeline (upload → chunk → embed → store)
# ---------------------------------------------------------------------------


@router.post(
    "/ingest/{doc_id}",
    response_model=UpsertResult,
    summary="Ingest a document into the vector store",
    description=(
        "Reads an already-uploaded document, chunks it, embeds each chunk "
        "via Gemini, and upserts the vectors into ChromaDB.  "
        "Must be called before a document can be queried via RAG."
    ),
    tags=["RAG"],
)
async def ingest_document(
    doc_id: str = Path(description="UUID of the uploaded document."),
    collection: str | None = None,
    doc_service: DocumentService = Depends(get_document_service),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    vector_store: VectorStoreService = Depends(get_vector_store_service),
) -> UpsertResult:
    """
    Full ingestion pipeline for a single document.

    Steps
    -----
    1. Load ``DocumentRecord`` from the document service.
    2. Read PDF bytes from disk.
    3. Chunk with ``ChunkingService``.
    4. Embed all chunks with ``EmbeddingService``.
    5. Upsert embeddings into ChromaDB via ``VectorStoreService``.
    """
    # 1. Resolve document record
    records = (await doc_service.list_documents()).documents
    record = next((r for r in records if r.id == doc_id), None)
    if record is None:
        raise NotFoundError("Document", doc_id)

    logger.info(f"Ingest start | doc_id={doc_id} | filename={record.original_filename}")

    # 2. Read PDF bytes
    from pathlib import Path as _Path
    # The upload_path is stored in the internal DocumentRecord but
    # DocumentResponse (the public model) does not expose it.
    # Re-resolve via the storage layout: {upload_dir}/{doc_id}/{filename}
    upload_root = doc_service._root  # noqa: SLF001
    pdf_path = upload_root / doc_id / record.filename
    if not pdf_path.exists():
        raise NotFoundError("PDF file", str(pdf_path))

    pdf_bytes = pdf_path.read_bytes()

    # 3. Chunk
    chunking_svc = ChunkingService()
    chunking_result = await chunking_svc.chunk_document(
        document_id=doc_id,
        pdf_content=pdf_bytes,
        original_filename=record.original_filename,
    )
    logger.info(f"Chunking done | doc_id={doc_id} | chunks={chunking_result.total_chunks}")

    # 4. Embed
    embedding_result = await embedding_service.embed_chunks(
        document_id=doc_id,
        chunks=chunking_result.chunks,
    )
    logger.info(
        f"Embedding done | doc_id={doc_id} | "
        f"succeeded={embedding_result.succeeded} | failed={embedding_result.failed}"
    )

    # 5. Upsert into ChromaDB
    # Only upsert successfully embedded chunks
    emb_map = {e.chunk_id: e for e in embedding_result.embeddings}
    matched_chunks = [c for c in chunking_result.chunks if c.chunk_id in emb_map]
    matched_embeddings = [emb_map[c.chunk_id] for c in matched_chunks]

    result = await vector_store.upsert_from_chunks_and_embeddings(
        chunks=matched_chunks,
        embeddings=matched_embeddings,
        document_id=doc_id,
        collection_name=collection,
    )

    logger.info(
        f"Ingest complete | doc_id={doc_id} | upserted={result.upserted} | "
        f"collection={result.collection}"
    )
    return result


@router.post(
    "/reindex/{doc_id}",
    response_model=UpsertResult,
    summary="Re-index and update embeddings for a document",
    description=(
        "Purges existing chunks for doc_id from ChromaDB and re-runs the "
        "chunking + embedding pipeline to update vector store embeddings."
    ),
    tags=["RAG"],
)
async def reindex_document(
    doc_id: str = Path(description="UUID of the document to re-index."),
    collection: str | None = None,
    doc_service: DocumentService = Depends(get_document_service),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    vector_store: VectorStoreService = Depends(get_vector_store_service),
) -> UpsertResult:
    logger.info(f"Re-index requested for document | doc_id={doc_id}")

    # 1. Purge existing vectors for doc_id if present
    try:
        await vector_store.delete_document(doc_id, collection_name=collection)
        logger.info(f"Purged old embeddings for re-indexing | doc_id={doc_id}")
    except Exception as exc:
        logger.debug(f"Purge before re-index skipped | doc_id={doc_id} | {exc}")

    # 2. Run fresh ingestion
    return await ingest_document(
        doc_id=doc_id,
        collection=collection,
        doc_service=doc_service,
        embedding_service=embedding_service,
        vector_store=vector_store,
    )


@router.post(
    "/ai-features",
    response_model=RAGResponse,
    summary="Generate AI Document Features (Summary, Flashcards, Quiz, Notes, Key Topics, FAQ)",
    description=(
        "Uses the RAG retrieval and Gemini LLM pipeline to generate structured AI "
        "features for a document or collection."
    ),
    tags=["RAG"],
)
async def generate_ai_feature_endpoint(
    req: AIFeatureRequest,
    service: RAGService = Depends(get_rag_service),
) -> RAGResponse:
    logger.info(f"AI Feature requested: {req.feature.value} | doc_id={req.document_id}")
    return await service.generate_ai_feature(
        feature=req.feature.value,
        document_id=req.document_id,
        collection=req.collection,
    )


