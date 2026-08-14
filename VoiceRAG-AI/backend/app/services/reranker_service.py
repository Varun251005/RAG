"""
Lightweight CPU Reranking Service for VoiceRAG AI.

Uses CrossEncoder ("cross-encoder/ms-marco-MiniLM-L-6-v2") on CPU to re-score
and re-rank candidate document chunks returned by hybrid retrieval.
"""

from __future__ import annotations

import time
from typing import Any
from loguru import logger

from app.core.config import get_settings


class RerankerService:
    """
    CPU-friendly passage reranker using sentence-transformers CrossEncoder.
    """

    def __init__(self, model_name: str | None = None, device: str = "cpu") -> None:
        cfg = get_settings()
        self.model_name = model_name or getattr(cfg, "reranker_model_name", "cross-encoder/ms-marco-MiniLM-L-6-v2")
        self.device = device
        self._model: Any | None = None

    def _get_model(self) -> Any:
        """Lazy loader for CrossEncoder model to avoid unnecessary memory overhead on start."""
        if self._model is None:
            logger.info(f"Loading CrossEncoder model '{self.model_name}' on device='{self.device}'...")
            start = time.time()
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self.model_name, device=self.device)
            elapsed = time.time() - start
            logger.info(f"CrossEncoder model loaded successfully in {elapsed:.2f}s")
        return self._model

    def rerank(
        self,
        question: str,
        candidates: list[Any],
        top_k: int = 5,
    ) -> list[Any]:
        """
        Rerank a list of candidate chunks against the user question.

        Parameters
        ----------
        question : str
            Natural language question query.
        candidates : list[Any]
            Candidate RetrievedChunk objects from hybrid retrieval.
        top_k : int
            Number of top reranked chunks to return.

        Returns
        -------
        list[Any]
            Top-K reranked chunk objects sorted descending by reranker_score.
        """
        clean_question = (question or "").strip()
        if not clean_question or not candidates or top_k < 1:
            return []

        model = self._get_model()

        # Construct (question, chunk_text) sentence pairs for CrossEncoder
        pairs = [(clean_question, str(chunk.text)) for chunk in candidates]

        start_time = time.time()
        raw_scores = model.predict(pairs)
        inference_ms = (time.time() - start_time) * 1000.0

        logger.debug(
            f"Reranking complete | candidates={len(candidates)} | "
            f"inference_time={inference_ms:.2f}ms"
        )

        reranked: list[Any] = []
        for idx, chunk in enumerate(candidates):
            score = float(raw_scores[idx]) if idx < len(raw_scores) else 0.0
            # Copy chunk and update reranker_score
            updated_chunk = chunk.model_copy()
            updated_chunk.reranker_score = round(score, 4)
            reranked.append((updated_chunk, score))

        # Sort descending by reranker cross-encoder score
        reranked.sort(key=lambda item: item[1], reverse=True)

        # Return final top_k chunk objects
        return [item[0] for item in reranked[:top_k]]
