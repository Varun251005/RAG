"""
RAG Service — Retrieval-Augmented Generation pipeline.

Pipeline
--------
1.  Embed the user question via ``EmbeddingService.embed_text``.
2.  Search ChromaDB via ``VectorStoreService.search`` → top-k chunks.
3.  Filter chunks below the score threshold.
4.  Build a formatted context string from the retrieved chunks.
5.  Feed context + question through a LangChain ``ChatPromptTemplate``
    piped to ``ChatGoogleGenerativeAI`` (Gemini) and ``StrOutputParser``.
6.  Return a ``RAGResponse`` (batch) **or** stream SSE events (streaming).

Streaming SSE format
--------------------
Each line yielded by ``stream_query`` is a complete SSE message::

    event: token\\ndata: {"text": "...token..."}\\n\\n
    event: sources\\ndata: {"sources": [...], "total_chunks_used": 5}\\n\\n
    event: done\\ndata: {}\\n\\n
    event: error\\ndata: {"detail": "..."}\\n\\n   ← only on failure

Configuration (``app.core.config.Settings``)
--------------------------------------------
    GEMINI_API_KEY         — Gemini API key (shared with embedding service).
    GEMINI_MODEL           — Chat model name (default: gemini-2.0-flash).
    RAG_TOP_K              — Chunks retrieved per query (default: 5).
    RAG_MAX_OUTPUT_TOKENS  — Max generation tokens (default: 2048).
    RAG_TEMPERATURE        — Temperature for generation (default: 0.2).
    RAG_SCORE_THRESHOLD    — Min cosine score to include a chunk (default: 0.0).
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from langchain_google_genai import ChatGoogleGenerativeAI
from loguru import logger

from app.core.config import get_settings
from app.core.exceptions import ServiceError, UnprocessableError
from app.models.rag import (
    RAGQuery,
    RAGResponse,
    RAGSource,
    RAGStreamError,
    RAGStreamSources,
    RAGStreamToken,
)
from app.models.vector_store import SearchResponse, SearchResult

if TYPE_CHECKING:
    from app.services.embedding_service import EmbeddingService
    from app.services.vector_store_service import VectorStoreService


# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a precise, factual assistant that answers questions exclusively using the provided document context.

Rules:
1. Answer ONLY using the information in the Context section below.
2. If the context does not contain sufficient information, respond with exactly:
   "I don't have enough information in the provided documents to answer this question."
3. Do not speculate, invent facts, or use knowledge outside the provided context.
4. Be concise, structured, and cite relevant details from the context when useful.
5. If multiple context chunks are relevant, synthesise them into a coherent answer.

Context:
{context}"""

_HUMAN_PROMPT = "{question}"

# Snippet length shown in RAGSource citations.
_SNIPPET_LENGTH = 250


class RAGService:
    """
    Production-grade Retrieval-Augmented Generation service.

    Parameters
    ----------
    embedding_service :
        Provides ``embed_text`` to vectorise the incoming question.
    vector_store_service :
        Provides ``search`` and ``search_by_document`` to retrieve chunks.
    api_key :
        Gemini API key.  Defaults to ``Settings.gemini_api_key``.
    model :
        Chat model name.  Defaults to ``Settings.gemini_model``.
    top_k :
        Default number of chunks to retrieve.
    max_output_tokens :
        Maximum generation tokens.
    temperature :
        Generation temperature (0 = deterministic, 1 = creative).
    score_threshold :
        Minimum cosine similarity score required for a chunk to be included.
    """

    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
        vector_store_service: VectorStoreService | None = None,
        api_key: str | None = None,
        model: str | None = None,
        top_k: int | None = None,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
        score_threshold: float | None = None,
    ) -> None:
        cfg = get_settings()

        if embedding_service is None:
            from app.api.deps import get_embedding_service
            self._embedding_svc = get_embedding_service()
        else:
            self._embedding_svc = embedding_service

        if vector_store_service is None:
            from app.api.deps import get_vector_store_service
            self._vector_store_svc = get_vector_store_service()
        else:
            self._vector_store_svc = vector_store_service

        self._api_key: str = api_key or cfg.gemini_api_key
        self._model: str = model or cfg.gemini_model
        self._top_k: int = top_k if top_k is not None else cfg.rag_top_k
        self._max_output_tokens: int = (
            max_output_tokens if max_output_tokens is not None else cfg.rag_max_output_tokens
        )
        self._temperature: float = (
            temperature if temperature is not None else cfg.rag_temperature
        )
        self._score_threshold: float = (
            score_threshold if score_threshold is not None else cfg.rag_score_threshold
        )

        # Lazily-built LangChain chain — cached after first creation.
        self._chain: Runnable | None = None

        logger.debug(
            f"RAGService initialised | model={self._model} | "
            f"top_k={self._top_k} | temperature={self._temperature}"
        )

    # ── Public: batch ──────────────────────────────────────────────────────────

    async def query(
        self,
        question: str,
        collection: str | None = None,
        top_k: int | None = None,
        document_id: str | None = None,
    ) -> RAGResponse:
        """
        Run a full RAG query and return the complete answer synchronously.

        Parameters
        ----------
        question :
            Natural-language question.
        collection :
            ChromaDB collection to search (``None`` → service default).
        top_k :
            Override the default number of retrieved chunks.
        document_id :
            Restrict retrieval to chunks from one document (optional).

        Returns
        -------
        RAGResponse
            Contains ``answer``, ``sources``, and metadata.
        """
        self._validate_question(question)

        search_resp, context = await self._retrieve(
            question=question,
            collection=collection,
            top_k=top_k or self._top_k,
            document_id=document_id,
        )
        sources = self._build_sources(search_resp.results)

        chain = self._get_chain()
        logger.info(f"RAG batch query | chunks={len(sources)} | model={self._model}")

        try:
            answer: str = await chain.ainvoke(
                {"context": context, "question": question}
            )
        except Exception as exc:
            logger.error(f"LLM invocation failed | {exc!r}")
            raise ServiceError(f"Generation failed: {exc}") from exc

        logger.info(
            f"RAG batch complete | answer_len={len(answer)} | sources={len(sources)}"
        )

        return RAGResponse(
            question=question,
            answer=answer.strip(),
            sources=sources,
            total_chunks_used=len(sources),
            model=self._model,
        )

    # ── Public: streaming ──────────────────────────────────────────────────────

    async def stream_query(
        self,
        question: str,
        collection: str | None = None,
        top_k: int | None = None,
        document_id: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Run a RAG query and stream the answer as Server-Sent Events.

        Yields one SSE-formatted string per event::

            event: token\\ndata: {"text": "..."}\\n\\n
            event: sources\\ndata: {"sources": [...], "total_chunks_used": N}\\n\\n
            event: done\\ndata: {}\\n\\n

        On error yields::

            event: error\\ndata: {"detail": "..."}\\n\\n

        Parameters match :meth:`query`.
        """
        # Validate
        try:
            self._validate_question(question)
        except UnprocessableError as exc:
            yield _sse("error", RAGStreamError(detail=exc.detail).model_dump())
            return

        # Step 1 & 2 — embed + retrieve
        try:
            search_resp, context = await self._retrieve(
                question=question,
                collection=collection,
                top_k=top_k or self._top_k,
                document_id=document_id,
            )
        except Exception as exc:
            logger.error(f"RAG retrieval failed | {exc!r}")
            yield _sse("error", RAGStreamError(detail=str(exc)).model_dump())
            return

        sources = self._build_sources(search_resp.results)
        logger.info(
            f"RAG stream query | chunks={len(sources)} | model={self._model}"
        )

        # Step 3 — stream LLM tokens
        chain = self._get_chain()
        try:
            async for token in chain.astream(
                {"context": context, "question": question}
            ):
                if token:
                    yield _sse("token", RAGStreamToken(text=token).model_dump())
        except Exception as exc:
            logger.error(f"LLM streaming failed | {exc!r}")
            yield _sse("error", RAGStreamError(detail=str(exc)).model_dump())
            return

        # Step 4 — emit sources + done
        yield _sse(
            "sources",
            RAGStreamSources(
                sources=sources,
                total_chunks_used=len(sources),
            ).model_dump(),
        )
        yield _sse("done", {})
        logger.info(f"RAG stream complete | sources={len(sources)}")

    # ── Public: AI Features ───────────────────────────────────────────────────

    async def generate_ai_feature(
        self,
        feature: str,
        document_id: str | None = None,
        collection: str | None = None,
    ) -> RAGResponse:
        """
        Generate grounded AI document features (Summary, Flashcards, Quiz, Notes, Key Topics, FAQ)
        using local hybrid retrieval (all-MiniLM-L6-v2 + ChromaDB + BM25 + Reranker) and Grok LLM
        (with local Qwen 2.5 0.5B fallback).
        """
        feature_prompts = {
            "summary": "Provide a comprehensive, highly structured executive summary of the document, including Key Takeaways and Core Insights.",
            "flashcards": "Generate 6 high-yield study flashcards based on the document context. Format each flashcard clearly with Front (Question/Concept) and Back (Answer/Explanation).",
            "quiz": "Generate a 5-question practice quiz based on the document. For each question, provide 4 options (A, B, C, D), indicate the correct answer, and give a brief explanation.",
            "notes": "Generate structured, organized study notes formatted in markdown with headers, bullet points, key definitions, and summary sections.",
            "key_topics": "Extract and explain the top 5 core topics, main themes, and key concepts presented in the document.",
            "faq": "Generate a list of 6 Frequently Asked Questions (FAQ) and detailed, clear answers grounded in the document.",
        }

        feature_key = feature.lower()
        prompt_question = feature_prompts.get(feature_key, "Provide a detailed summary and overview of the document.")
        logger.info(f"Generating AI Feature: {feature} | doc_id={document_id}")

        from app.api.deps import get_retrieval_service, get_grok_service, get_ollama_llm_service

        retrieval_svc = get_retrieval_service()
        grok_svc = get_grok_service()
        ollama_svc = get_ollama_llm_service()

        # 1. Retrieve chunks locally via all-MiniLM-L6-v2 + ChromaDB + BM25 + Reranker
        retrieved_chunks = await retrieval_svc.retrieve_relevant_chunks(
            question=prompt_question,
            top_k=10,
            document_id=document_id,
            collection_name=collection,
        )

        # 2. Try Grok LLM first if API key configured
        model_name = "grok-2-latest"
        answer = ""
        sources = []

        if grok_svc.api_key:
            try:
                grok_res = await grok_svc.generate_feature_from_chunks(
                    feature_prompt=prompt_question,
                    retrieved_chunks=retrieved_chunks,
                )
                answer = grok_res.answer
                model_name = grok_res.model_name
                sources = [
                    RAGSource(
                        chunk_id=src.chunk_id,
                        snippet="",
                        page_number=src.page_number,
                        original_filename=src.filename,
                        score=1.0,
                        document_id=src.document_id,
                    )
                    for src in grok_res.sources
                ]
            except Exception as grok_err:
                logger.warning(f"Grok API failed for AI feature '{feature}', falling back to local Qwen LLM: {grok_err}")
                answer = ""

        # 3. Fallback to local Qwen LLM if Grok didn't return an answer
        if not answer:
            qwen_res = await ollama_svc.generate_rag_answer(
                question=prompt_question,
                retrieved_chunks=retrieved_chunks,
            )
            answer = qwen_res.answer
            model_name = f"Local Qwen ({qwen_res.model_name})"
            sources = [
                RAGSource(
                    chunk_id=src.chunk_id,
                    snippet="",
                    page_number=src.page_number,
                    original_filename=src.filename,
                    score=1.0,
                    document_id=src.document_id,
                )
                for src in qwen_res.sources
            ]

        return RAGResponse(
            question=prompt_question,
            answer=answer,
            sources=sources,
            total_chunks_used=len(sources),
            model=model_name,
        )



    # ── Private: retrieval ─────────────────────────────────────────────────────

    async def _retrieve(
        self,
        question: str,
        collection: str | None,
        top_k: int,
        document_id: str | None,
    ) -> tuple[SearchResponse, str]:
        """
        Embed *question*, search ChromaDB, filter by score threshold.

        Returns ``(SearchResponse, context_string)``.
        """
        # Embed question
        logger.debug(f"Embedding question | len={len(question)}")
        try:
            vector = await self._embedding_svc.embed_text(question)
        except Exception as exc:
            raise ServiceError(f"Failed to embed question: {exc}") from exc

        # Search
        logger.debug(f"Searching ChromaDB | top_k={top_k} | doc_filter={document_id}")
        try:
            if document_id:
                search_resp = await self._vector_store_svc.search_by_document(
                    query_vector=vector,
                    document_id=document_id,
                    query_text=question,
                    n_results=top_k,
                    collection_name=collection,
                )
            else:
                search_resp = await self._vector_store_svc.search(
                    query_vector=vector,
                    query_text=question,
                    n_results=top_k,
                    collection_name=collection,
                )
        except Exception as exc:
            raise ServiceError(f"ChromaDB search failed: {exc}") from exc

        # Filter by score threshold
        filtered = [
            r for r in search_resp.results if r.score >= self._score_threshold
        ]
        logger.debug(
            f"Retrieval | total={len(search_resp.results)} "
            f"above_threshold={len(filtered)} | threshold={self._score_threshold}"
        )

        # Re-wrap in a SearchResponse with filtered results
        from app.models.vector_store import SearchResponse as SR
        filtered_resp = SR(
            query=search_resp.query,
            collection=search_resp.collection,
            results=filtered,
            total_returned=len(filtered),
        )

        context = self._build_context(filtered)
        return filtered_resp, context

    # ── Private: helpers ───────────────────────────────────────────────────────

    def _build_context(self, results: list[SearchResult]) -> str:
        """Format retrieved chunks into a numbered context block."""
        if not results:
            return "No relevant context found in the documents."

        parts: list[str] = []
        for i, result in enumerate(results, 1):
            page = result.metadata.get("page_number", "?")
            filename = result.metadata.get("original_filename", "unknown")
            parts.append(
                f"[Chunk {i} | {filename} | page {page}]\n{result.text}"
            )

        return "\n\n" + ("\n\n---\n\n".join(parts)) + "\n"

    def _build_sources(self, results: list[SearchResult]) -> list[RAGSource]:
        """Convert ``SearchResult`` objects to ``RAGSource`` citations."""
        sources: list[RAGSource] = []
        for result in results:
            meta = result.metadata
            sources.append(
                RAGSource(
                    chunk_id=result.id,
                    snippet=result.text[:_SNIPPET_LENGTH],
                    page_number=int(meta.get("page_number", 1)),
                    original_filename=str(meta.get("original_filename", "unknown")),
                    score=round(result.score, 4),
                    document_id=str(meta.get("document_id", "")),
                )
            )
        return sources

    def _validate_question(self, question: str) -> None:
        """Raise ``UnprocessableError`` for blank or excessively long questions."""
        if not question.strip():
            raise UnprocessableError("Question must not be blank.")
        if len(question) > 2000:
            raise UnprocessableError(
                f"Question is too long ({len(question)} chars, max 2000)."
            )

    def _get_chain(self) -> Runnable:
        """
        Return the lazily-built LangChain LCEL chain.

        Chain shape: ``prompt | llm | StrOutputParser``

        The chain is cached on the instance; the LLM client is shared for
        the process lifetime.
        """
        if self._chain is None:
            if not self._api_key:
                raise ServiceError(
                    "GEMINI_API_KEY is not configured. "
                    "Set it in your .env file or environment."
                )

            llm = ChatGoogleGenerativeAI(
                model=self._model,
                google_api_key=self._api_key,  # type: ignore[arg-type]
                temperature=self._temperature,
                max_output_tokens=self._max_output_tokens,
            )

            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", _SYSTEM_PROMPT),
                    ("human", _HUMAN_PROMPT),
                ]
            )

            self._chain = prompt | llm | StrOutputParser()
            logger.debug(f"LangChain chain built | model={self._model}")

        return self._chain


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _sse(event: str, data: dict) -> str:
    """
    Format a single Server-Sent Event string.

    Output::

        event: <event>\\ndata: <json>\\n\\n
    """
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
