"""
Grok (xAI) LLM Generation Service for VoiceRAG AI Studio.

Uses the xAI REST API (OpenAI-compatible /v1/chat/completions) to generate
high-quality, grounded AI Studio outputs (Summary, Flashcards, Quiz, Notes, Key Topics, FAQ)
using document chunks retrieved from the local RAG pipeline.
"""

from __future__ import annotations

import time
import httpx
from loguru import logger
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.exceptions import ServiceError
from app.services.llm_service import SourceReference, RAGAnswerResponse
from app.services.retrieval_service import RetrievedChunk


class GrokLLMService:
    """
    Grok (xAI) LLM Service for AI Studio feature synthesis.
    """

    SYSTEM_PROMPT = (
        "You are an expert AI document analyst for VoiceRAG AI Studio.\n"
        "Your task is to generate structured, accurate, and insightful outputs based ONLY on the provided document context.\n"
        "RULES:\n"
        "1. Ground all findings, facts, concepts, and answers strictly in the provided document context.\n"
        "2. Do NOT invent, assume, or extrapolate facts outside the context.\n"
        "3. Provide rich, well-formatted Markdown with clean headers, bullet points, and structure."
    )

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model_name: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> None:
        cfg = get_settings()
        self.api_key = api_key or cfg.grok_api_key
        self.base_url = (base_url or cfg.grok_base_url).rstrip("/")
        self.model_name = model_name or cfg.grok_model
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

    async def generate_completion(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> str:
        """
        Send a raw prompt to Grok API and return the string content response.
        """
        if not self.api_key:
            raise ServiceError("Grok API Key is missing.")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt or self.SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        endpoint = f"{self.base_url}/chat/completions"

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                res = await client.post(endpoint, json=payload, headers=headers)

            if res.status_code != 200:
                raise ServiceError(f"Grok API returned status {res.status_code}: {res.text}")

            data = res.json()
            choices = data.get("choices", [])
            if not choices:
                raise ServiceError("Grok API returned empty choices response.")

            answer = choices[0].get("message", {}).get("content", "").strip()
            return answer

        except Exception as exc:
            if isinstance(exc, ServiceError):
                raise
            raise ServiceError(f"Grok API invocation failed for model '{self.model_name}': {exc}") from exc

    async def generate_feature_from_chunks(
        self,
        feature_prompt: str,
        retrieved_chunks: list[RetrievedChunk],
    ) -> RAGAnswerResponse:
        """
        Generate grounded AI Studio output from retrieved chunks using Grok API.
        """
        context_str, sources = self.build_context(retrieved_chunks)

        user_prompt = (
            f"Context Documents:\n"
            f"---\n"
            f"{context_str}\n"
            f"---\n\n"
            f"Task: {feature_prompt}\n\n"
            f"Result:"
        )

        start_time = time.perf_counter()
        raw_answer = await self.generate_completion(prompt=user_prompt)
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        logger.info(
            f"Generated Grok AI Studio feature | model={self.model_name} | "
            f"time_ms={elapsed_ms:.1f} | chunks={len(retrieved_chunks)}"
        )

        return RAGAnswerResponse(
            answer=raw_answer,
            sources=sources,
            model_name=f"Grok ({self.model_name})",
            generation_time_ms=elapsed_ms,
            context_chunks_used=len(retrieved_chunks),
        )
