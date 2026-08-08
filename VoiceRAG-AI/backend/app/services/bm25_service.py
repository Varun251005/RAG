"""
BM25 Keyword Search Service for VoiceRAG AI.

Provides lightweight, CPU-only keyword retrieval over document chunks using rank-bm25.
Maintains in-memory document chunk index synchronized with document operations.
"""

from __future__ import annotations

import re
from typing import Any
from loguru import logger
from pydantic import BaseModel


class BM25Document(BaseModel):
    """Structured representation of a document chunk indexed in BM25."""

    chunk_id: str
    text: str
    document_id: str
    source_filename: str
    page_number: int
    chunk_index: int


def tokenize_text(text: str) -> list[str]:
    """Lightweight whitespace & word tokenization for BM25 indexing."""
    if not text:
        return []
    return re.findall(r"\w+", text.lower())


class BM25Service:
    """
    In-memory BM25 keyword retrieval engine maintaining chunk consistency.
    """

    def __init__(self) -> None:
        self._documents: dict[str, BM25Document] = {}  # chunk_id -> BM25Document
        self._corpus_tokens: list[list[str]] = []
        self._doc_ids_order: list[str] = []  # parallel list of chunk_ids
        self._bm25: Any | None = None

    def _rebuild_index(self) -> None:
        """Re-initialize BM25Okapi with the current corpus of documents."""
        from rank_bm25 import BM25Okapi

        self._doc_ids_order = list(self._documents.keys())
        if not self._doc_ids_order:
            self._corpus_tokens = []
            self._bm25 = None
            return

        self._corpus_tokens = [
            tokenize_text(self._documents[cid].text) for cid in self._doc_ids_order
        ]
        self._bm25 = BM25Okapi(self._corpus_tokens)
        logger.debug(f"BM25 index rebuilt | total_chunks={len(self._doc_ids_order)}")

    def add_documents(self, documents: list[BM25Document]) -> None:
        """
        Add or update document chunks in the BM25 index.
        Idempotent: Replaces existing chunks with identical chunk_id to avoid duplicates.
        """
        if not documents:
            return

        for doc in documents:
            self._documents[doc.chunk_id] = doc

        self._rebuild_index()
        logger.info(
            f"BM25 index updated | added/updated_chunks={len(documents)} | total_chunks={len(self._documents)}"
        )

    def delete_document(self, document_id: str) -> None:
        """
        Remove all document chunks associated with document_id from the BM25 index.
        """
        to_delete = [
            cid for cid, doc in self._documents.items() if doc.document_id == document_id
        ]
        if not to_delete:
            return

        for cid in to_delete:
            del self._documents[cid]

        self._rebuild_index()
        logger.info(
            f"BM25 index document deleted | document_id={document_id} | removed_chunks={len(to_delete)}"
        )

    def clear(self) -> None:
        """Clear all indexed documents."""
        self._documents.clear()
        self._corpus_tokens.clear()
        self._doc_ids_order.clear()
        self._bm25 = None

    def get_document_count(self) -> int:
        """Return total number of indexed document chunks."""
        return len(self._documents)

    def get_documents_by_doc_id(self, document_id: str) -> list[BM25Document]:
        """Return all indexed chunks belonging to a document_id."""
        return [doc for doc in self._documents.values() if doc.document_id == document_id]

    async def sync_from_vector_store(
        self, vector_store_service: Any, collection_name: str | None = None
    ) -> None:
        """
        Synchronize in-memory BM25 index with documents currently stored in ChromaDB.
        """
        try:
            col = await vector_store_service.get_or_create_collection(collection_name)
            raw = col.get(include=["metadatas", "documents"])
            ids = raw.get("ids") or []
            metadatas = raw.get("metadatas") or []
            documents = raw.get("documents") or []

            bm25_docs: list[BM25Document] = []
            for idx, cid in enumerate(ids):
                meta = metadatas[idx] if idx < len(metadatas) and metadatas[idx] else {}
                text = documents[idx] if idx < len(documents) else ""
                if not text:
                    continue
                bm25_docs.append(
                    BM25Document(
                        chunk_id=str(cid),
                        text=str(text),
                        document_id=str(meta.get("document_id", "")),
                        source_filename=str(meta.get("source_filename", "unknown.pdf")),
                        page_number=int(meta.get("page_number", 1)),
                        chunk_index=int(meta.get("chunk_index", 0)),
                    )
                )

            if bm25_docs:
                self.add_documents(bm25_docs)
                logger.info(f"BM25 synced from vector store | total={len(bm25_docs)}")
        except Exception as exc:
            logger.warning(f"BM25 sync from vector store skipped/failed: {exc}")

    def search(
        self,
        query: str,
        top_k: int = 5,
        document_id: str | None = None,
    ) -> list[tuple[BM25Document, float]]:
        """
        Query the BM25 index with a natural language query.
        Returns a list of (BM25Document, normalized_bm25_score) tuples sorted descending.
        Score range: [0.0, 1.0].
        """
        clean_query = (query or "").strip()
        if not clean_query or not self._bm25 or not self._doc_ids_order:
            return []

        query_tokens = tokenize_text(clean_query)
        if not query_tokens:
            return []

        raw_scores = self._bm25.get_scores(query_tokens)
        if len(raw_scores) == 0:
            return []

        candidates: list[tuple[BM25Document, float]] = []
        max_score = 0.0

        for idx, chunk_id in enumerate(self._doc_ids_order):
            doc = self._documents[chunk_id]
            if document_id and doc.document_id != document_id:
                continue
            score = float(raw_scores[idx])
            if score > 0.0:
                if score > max_score:
                    max_score = score
                candidates.append((doc, score))

        if not candidates or max_score <= 0.0:
            return []

        normalized_results: list[tuple[BM25Document, float]] = []
        for doc, score in candidates:
            norm_score = max(0.0, min(1.0, score / max_score))
            normalized_results.append((doc, norm_score))

        normalized_results.sort(key=lambda item: item[1], reverse=True)
        return normalized_results[:top_k]
