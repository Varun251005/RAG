"""
RAG Retrieval Service for VoiceRAG AI.

Provides Hybrid (Semantic Vector + BM25 Keyword) retrieval over document chunks
using 384-dimensional CPU embeddings (all-MiniLM-L6-v2) and rank-bm25, followed
by optional CPU CrossEncoder passage reranking (cross-encoder/ms-marco-MiniLM-L-6-v2).
"""

from __future__ import annotations

from typing import Any
from loguru import logger
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.exceptions import UnprocessableError
from app.services.bm25_service import BM25Document, BM25Service
from app.services.local_embedding_service import LocalEmbeddingService
from app.services.reranker_service import RerankerService
from app.services.vector_store_service import VectorStoreService


class RetrievedChunk(BaseModel):
    """Structured result representation of a retrieved document chunk."""

    chunk_id: str
    text: str
    document_id: str
    source_filename: str
    page_number: int
    chunk_index: int
    distance: float
    similarity_score: float = Field(
        ..., description="Relevance score in range [0.0, 1.0]"
    )
    reranker_score: float | None = Field(
        default=None, description="Optional raw score assigned by CrossEncoder reranker"
    )


class RAGRetrievalService:
    """
    Hybrid Retrieval Service combining semantic vector search (ChromaDB + all-MiniLM-L6-v2)
    and BM25 keyword search with weighted score fusion, followed by CrossEncoder passage reranking.
    """

    def __init__(
        self,
        embedding_service: LocalEmbeddingService | None = None,
        vector_store_service: VectorStoreService | None = None,
        bm25_service: BM25Service | None = None,
        reranker_service: RerankerService | None = None,
        retrieval_mode: str | None = None,
        vector_weight: float | None = None,
        keyword_weight: float | None = None,
        reranker_enabled: bool | None = None,
        candidate_k: int | None = None,
    ) -> None:

        cfg = get_settings()
        self.embedding_service = embedding_service or LocalEmbeddingService()
        from fastapi.params import Depends


        if vector_store_service is None or isinstance(vector_store_service, Depends):
            from app.api.deps import get_vector_store_service
            self.vector_store_service = get_vector_store_service()
        else:
            self.vector_store_service = vector_store_service

        if bm25_service is None or isinstance(bm25_service, Depends):
            from app.api.deps import get_bm25_service
            self.bm25_service = get_bm25_service()
        else:
            self.bm25_service = bm25_service


        if reranker_service is None or isinstance(reranker_service, Depends):
            from app.api.deps import get_reranker_service
            self.reranker_service = get_reranker_service()
        else:
            self.reranker_service = reranker_service


        self.retrieval_mode = retrieval_mode or getattr(cfg, "retrieval_mode", "hybrid")
        self.vector_weight = vector_weight if vector_weight is not None else getattr(cfg, "vector_weight", 0.7)
        self.keyword_weight = keyword_weight if keyword_weight is not None else getattr(cfg, "keyword_weight", 0.3)
        self.reranker_enabled = reranker_enabled if reranker_enabled is not None else getattr(cfg, "reranker_enabled", True)
        self.candidate_k = candidate_k if candidate_k is not None else getattr(cfg, "reranker_candidate_k", 15)

    async def retrieve_relevant_chunks(
        self,
        question: str,
        top_k: int = 5,
        score_threshold: float | None = None,
        document_id: str | None = None,
        collection_name: str | None = None,
        mode: str | None = None,
        vector_weight: float | None = None,
        keyword_weight: float | None = None,
        reranker_enabled: bool | None = None,
        candidate_k: int | None = None,
    ) -> list[RetrievedChunk]:
        """
        Retrieve relevant document chunks using hybrid (semantic + keyword) retrieval and CPU reranking.
        Supports document_id filtering, score normalization, result fusion, CrossEncoder reranking, and Top-K.
        """
        clean_question = (question or "").strip()
        if not clean_question:
            raise UnprocessableError("Question text cannot be empty.")

        if top_k < 1:
            return []

        eff_mode = (mode or self.retrieval_mode or "hybrid").lower()
        vw = vector_weight if vector_weight is not None else self.vector_weight
        kw = keyword_weight if keyword_weight is not None else self.keyword_weight
        use_reranker = reranker_enabled if reranker_enabled is not None else self.reranker_enabled
        eff_candidate_k = candidate_k if candidate_k is not None else (self.candidate_k if use_reranker else top_k)
        eff_candidate_k = max(eff_candidate_k, top_k)

        # Auto-sync BM25 from vector store if BM25 index is empty
        if self.bm25_service.get_document_count() == 0:
            await self.bm25_service.sync_from_vector_store(self.vector_store_service, collection_name)

        vector_map: dict[str, tuple[dict[str, Any], str, float]] = {}
        keyword_map: dict[str, tuple[BM25Document, float]] = {}

        # 1. Semantic Vector Search
        if eff_mode in ("hybrid", "vector") and vw > 0.0:
            query_embedding = self.embedding_service.embed_text(clean_question)
            where_filter = {"document_id": document_id} if document_id else None

            search_response = await self.vector_store_service.search(
                query_vector=query_embedding,
                query_text=clean_question,
                n_results=eff_candidate_k * 2,
                where=where_filter,
                collection_name=collection_name,
            )

            for item in search_response.results:
                dist = float(item.distance)
                sim_score = max(0.0, min(1.0, 1.0 - dist))
                chunk_meta = item.metadata or {}
                vector_map[item.id] = (chunk_meta, item.text, sim_score)

        # 2. BM25 Keyword Search
        if eff_mode in ("hybrid", "keyword") and kw > 0.0:
            bm25_results = self.bm25_service.search(
                query=clean_question,
                top_k=eff_candidate_k * 2,
                document_id=document_id,
            )

            for doc, bm_score in bm25_results:
                keyword_map[doc.chunk_id] = (doc, bm_score)

        # 3. Result Fusion & Duplicate Merging
        all_chunk_ids = set(vector_map.keys()) | set(keyword_map.keys())
        fused_chunks: list[RetrievedChunk] = []

        for cid in all_chunk_ids:
            vec_entry = vector_map.get(cid)
            kw_entry = keyword_map.get(cid)

            v_score = vec_entry[2] if vec_entry else 0.0
            k_score = kw_entry[1] if kw_entry else 0.0

            if vec_entry:
                chunk_meta, text, _ = vec_entry
                doc_id = str(chunk_meta.get("document_id", ""))
                filename = str(chunk_meta.get("source_filename", "unknown.pdf"))
                page_num = int(chunk_meta.get("page_number", 1))
                chunk_idx = int(chunk_meta.get("chunk_index", 0))
            else:
                b_doc, _ = kw_entry  # type: ignore[union-attr]
                text = b_doc.text
                doc_id = b_doc.document_id
                filename = b_doc.source_filename
                page_num = b_doc.page_number
                chunk_idx = b_doc.chunk_index

            if eff_mode == "vector":
                fused_score = v_score
            elif eff_mode == "keyword":
                fused_score = k_score
            else:
                total_weight = vw + kw
                if total_weight > 0:
                    fused_score = (vw * v_score + kw * k_score) / total_weight
                else:
                    fused_score = 0.0

            fused_score = max(0.0, min(1.0, fused_score))

            if score_threshold is not None and fused_score < score_threshold:
                continue

            retrieved_chunk = RetrievedChunk(
                chunk_id=cid,
                text=text,
                document_id=doc_id,
                source_filename=filename,
                page_number=page_num,
                chunk_index=chunk_idx,
                distance=max(0.0, 1.0 - fused_score),
                similarity_score=fused_score,
            )
            fused_chunks.append(retrieved_chunk)

        fused_chunks.sort(key=lambda r: r.similarity_score, reverse=True)
        candidate_pool = fused_chunks[:eff_candidate_k]

        # 4. CPU Passage Reranking
        if use_reranker and candidate_pool:
            reranked = self.reranker_service.rerank(
                question=clean_question,
                candidates=candidate_pool,
                top_k=top_k,
            )
            return reranked

        return candidate_pool[:top_k]
