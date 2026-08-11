"""
LLM Generation Service for VoiceRAG AI using local Qwen via Ollama on CPU.

Supports:
- Context building with document/chunk metadata
- Strict RAG grounding prompt enforcement
- Source attribution tracking
- Configurable model selection (defaults to lightweight qwen2.5:0.5b)
"""

from __future__ import annotations

import time
from typing import Any

import httpx
from loguru import logger
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.exceptions import ServiceError
from app.services.retrieval_service import RetrievedChunk


class SourceReference(BaseModel):
    """Source document reference returned alongside RAG generated answers."""

    document_id: str
    filename: str
    page_number: int
    chunk_id: str


class RAGAnswerResponse(BaseModel):
    """Structured response containing the grounded answer and source citations."""

    answer: str
    sources: list[SourceReference]
    model_name: str
    generation_time_ms: float
    context_chunks_used: int


class OllamaLLMService:
    """
    Service responsible for building RAG context prompts and generating
    factually grounded answers using a local Qwen model via Ollama.
    """

    SYSTEM_PROMPT = (
        "You are a strict, factual AI assistant for VoiceRAG AI.\n"
        "Your task is to answer the user's question using ONLY the provided document context below.\n"
        "RULES:\n"
        "1. Use ONLY the facts directly stated in the context.\n"
        "2. Do NOT invent, assume, or extrapolate information.\n"
        "3. Do NOT use outside general knowledge for document-specific questions.\n"
        "4. If the answer is not present in the context, you MUST respond with: "
        "\"The requested information is not available in the provided documents.\"\n"
        "5. Keep your answer factual, accurate, relevant, and concise."
    )

    def __init__(
        self,
        base_url: str | None = None,
        model_name: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> None:
        cfg = get_settings()
        self.base_url = (base_url or cfg.ollama_base_url).rstrip("/")
        self.model_name = model_name or cfg.ollama_model
        self.temperature = temperature if temperature is not None else cfg.rag_temperature
        self.max_tokens = max_tokens or cfg.rag_max_output_tokens

    def build_context(self, retrieved_chunks: list[RetrievedChunk]) -> tuple[str, list[SourceReference]]:
        """
        Combine retrieved chunks into a formatted context string and extract source citations.
        """
        context_blocks: list[str] = []
        sources: list[SourceReference] = []
        seen_source_keys: set[str] = set()

        for idx, chunk in enumerate(retrieved_chunks, start=1):
            block = (
                f"[Source {idx}]\n"
                f"Document ID: {chunk.document_id}\n"
                f"Filename: {chunk.source_filename}\n"
                f"Page: {chunk.page_number}\n"
                f"Chunk ID: {chunk.chunk_id}\n"
                f"Content:\n{chunk.text}\n"
            )
            context_blocks.append(block)

            source_key = f"{chunk.document_id}_{chunk.page_number}_{chunk.chunk_id}"
            if source_key not in seen_source_keys:
                seen_source_keys.add(source_key)
                sources.append(
                    SourceReference(
                        document_id=chunk.document_id,
                        filename=chunk.source_filename,
                        page_number=chunk.page_number,
                        chunk_id=chunk.chunk_id,
                    )
                )

        full_context = "\n---\n".join(context_blocks) if context_blocks else "No relevant document chunks found."
        return full_context, sources

    async def generate_rag_answer(
        self,
        question: str,
        retrieved_chunks: list[RetrievedChunk],
    ) -> RAGAnswerResponse:
        """
        Generate a grounded RAG answer for question based strictly on retrieved_chunks.
        """
        if not retrieved_chunks:
            return RAGAnswerResponse(
                answer="The requested information is not available in the provided documents.",
                sources=[],
                model_name=self.model_name,
                generation_time_ms=0.0,
                context_chunks_used=0,
            )

        context_str, sources = self.build_context(retrieved_chunks)

        user_prompt = (
            f"Context Documents:\n"
            f"---\n"
            f"{context_str}\n"
            f"---\n\n"
            f"User Question: {question}\n\n"
            f"Answer:"
        )

        payload = {
            "model": self.model_name,
            "system": self.SYSTEM_PROMPT,
            "prompt": user_prompt,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            },
        }

        start_time = time.perf_counter()
        endpoint = f"{self.base_url}/api/generate"

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                res = await client.post(endpoint, json=payload)

            if res.status_code != 200:
                raise ServiceError(f"Ollama API returned status {res.status_code}: {res.text}")

            response_data = res.json()
            raw_answer = response_data.get("response", "").strip()

            elapsed_ms = (time.perf_counter() - start_time) * 1000.0

            logger.info(
                f"Generated RAG answer | model={self.model_name} | "
                f"time_ms={elapsed_ms:.1f} | chunks={len(retrieved_chunks)}"
            )

            return RAGAnswerResponse(
                answer=raw_answer,
                sources=sources,
                model_name=self.model_name,
                generation_time_ms=elapsed_ms,
                context_chunks_used=len(retrieved_chunks),
            )

        except Exception as exc:
            if isinstance(exc, ServiceError):
                raise
            raise ServiceError(f"Failed to generate RAG answer via Ollama model '{self.model_name}': {exc}") from exc
