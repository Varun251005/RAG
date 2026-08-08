"""
Document Ingestion Service for VoiceRAG AI.

Orchestrates:
1. PDF validation & page-by-page text extraction (PDFProcessingService)
2. Text chunking & metadata tagging (ChunkingService)
3. Batch CPU embedding generation (LocalEmbeddingService with all-MiniLM-L6-v2)
4. Vector & metadata storage in ChromaDB (VectorStoreService)

Includes failure rollback handling and idempotent upsert capabilities.
"""

from __future__ import annotations

import uuid
from typing import Any

from loguru import logger

from app.core.exceptions import ServiceError, UnprocessableError
from app.models.vector_store import VectorDocument
from app.services.chunking_service import ChunkingService
from app.services.local_embedding_service import LocalEmbeddingService
from app.services.pdf_service import PDFProcessingService
from app.services.bm25_service import BM25Document, BM25Service
from app.services.vector_store_service import VectorStoreService


class DocumentIngestionService:
    """
    Orchestrates end-to-end PDF document ingestion into the VoiceRAG AI vector database.
    """

    def __init__(
        self,
        pdf_service: PDFProcessingService | None = None,
        chunking_service: ChunkingService | None = None,
        embedding_service: LocalEmbeddingService | None = None,
        vector_store_service: VectorStoreService | None = None,
        bm25_service: BM25Service | None = None,
    ) -> None:
        self.pdf_service = pdf_service or PDFProcessingService()
        self.chunking_service = chunking_service or ChunkingService(chunk_size=3200, chunk_overlap=600)
        self.embedding_service = embedding_service or LocalEmbeddingService()
        self.vector_store_service = vector_store_service or VectorStoreService()
        if bm25_service is None:
            from app.api.deps import get_bm25_service
            self.bm25_service = get_bm25_service()
        else:
            self.bm25_service = bm25_service

    async def ingest_pdf_bytes(
        self,
        pdf_bytes: bytes,
        filename: str,
        document_id: str | None = None,
        collection_name: str | None = None,
    ) -> dict[str, Any]:
        """
        Full ingestion pipeline: PDF → Pages → Chunks → Batch CPU Embeddings → ChromaDB.

        Idempotent: Upserts vectors using deterministic chunk IDs.
        Safe: Rollback cleans up partial ChromaDB vectors if any phase fails.
        """
        doc_id = document_id or f"doc_{uuid.uuid4().hex[:12]}"
        logger.info(f"Starting PDF ingestion | document_id={doc_id} | filename={filename}")

        try:
            # 1. Page-by-page PDF extraction
            pdf_data = self.pdf_service.extract_text_from_bytes(
                content=pdf_bytes,
                filename=filename,
                doc_id=doc_id,
            )
            pages = pdf_data["pages"]
            total_pages = pdf_data["total_pages"]

            # 2. Text Chunking across extracted pages
            raw_chunks: list[dict[str, Any]] = []
            global_chunk_idx = 0

            for page in pages:
                page_num = page["page_number"]
                page_text = page["text"]

                if not page_text.strip():
                    continue

                split_text_blocks = self.chunking_service._splitter.split_text(page_text)

                for within_page_idx, chunk_text in enumerate(split_text_blocks):
                    chunk_id = f"{doc_id}_p{page_num:04d}_c{within_page_idx:04d}"
                    raw_chunks.append({
                        "chunk_id": chunk_id,
                        "document_id": doc_id,
                        "source_filename": filename,
                        "page_number": page_num,
                        "chunk_index": global_chunk_idx,
                        "text": chunk_text,
                    })
                    global_chunk_idx += 1

            if not raw_chunks:
                raise UnprocessableError(f"No text chunks could be generated for document '{filename}'.")

            # 3. Batch CPU Embeddings (all-MiniLM-L6-v2, 384-dim)
            chunk_texts = [c["text"] for c in raw_chunks]
            embeddings = self.embedding_service.embed_batch(chunk_texts)

            if len(embeddings) != len(raw_chunks):
                raise ServiceError("Mismatch between generated embeddings count and chunks count.")

            # 4. Construct VectorDocuments
            vector_docs: list[VectorDocument] = []
            for idx, c in enumerate(raw_chunks):
                v_doc = VectorDocument(
                    id=c["chunk_id"],
                    embedding=embeddings[idx],
                    text=c["text"],
                    metadata={
                        "document_id": c["document_id"],
                        "source_filename": c["source_filename"],
                        "page_number": c["page_number"],
                        "chunk_index": c["chunk_index"],
                    },
                )
                vector_docs.append(v_doc)

            # 5. ChromaDB Vector Upsert & BM25 Keyword Indexing
            await self.vector_store_service.upsert_documents(
                documents=vector_docs,
                collection_name=collection_name,
                document_id=doc_id,
            )

            bm25_docs = [
                BM25Document(
                    chunk_id=c["chunk_id"],
                    text=c["text"],
                    document_id=c["document_id"],
                    source_filename=c["source_filename"],
                    page_number=c["page_number"],
                    chunk_index=c["chunk_index"],
                )
                for c in raw_chunks
            ]
            self.bm25_service.add_documents(bm25_docs)

            logger.info(
                f"Document ingestion successful | document_id={doc_id} | "
                f"pages={total_pages} | chunks={len(vector_docs)}"
            )

            return {
                "document_id": doc_id,
                "filename": filename,
                "total_pages": total_pages,
                "total_chunks": len(vector_docs),
                "status": "completed",
            }

        except Exception as exc:
            logger.error(f"Ingestion failed for document_id={doc_id}: {exc}. Performing rollback cleanup...")
            try:
                # Cleanup any partially indexed vectors/keywords for this document_id
                await self.vector_store_service.delete_document(
                    document_id=doc_id,
                    collection_name=collection_name,
                )
                self.bm25_service.delete_document(document_id=doc_id)
                logger.info(f"Rollback cleanup succeeded for document_id={doc_id}")
            except Exception as cleanup_exc:
                logger.warning(f"Rollback cleanup warning for document_id={doc_id}: {cleanup_exc}")
            raise exc
