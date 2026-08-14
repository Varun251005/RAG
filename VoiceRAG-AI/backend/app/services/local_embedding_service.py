"""
Local Embedding Service for VoiceRAG AI using Sentence Transformers.

Uses 'sentence-transformers/all-MiniLM-L6-v2' executing strictly on CPU.
Singleton model loading ensures model weights are loaded only once in memory.
"""

from __future__ import annotations

import time
from typing import ClassVar

from loguru import logger
from sentence_transformers import SentenceTransformer


class LocalEmbeddingService:
    """
    Service for generating normalized 384-dimensional text embeddings locally on CPU.
    """

    MODEL_NAME: ClassVar[str] = "sentence-transformers/all-MiniLM-L6-v2"
    EXPECTED_DIMENSION: ClassVar[int] = 384

    _model: ClassVar[SentenceTransformer | None] = None

    @classmethod
    def get_model(cls) -> SentenceTransformer:
        """
        Get or initialize the shared singleton SentenceTransformer model on CPU.
        """
        if cls._model is None:
            logger.info(f"Loading local embedding model '{cls.MODEL_NAME}' on CPU...")
            t0 = time.perf_counter()
            cls._model = SentenceTransformer(cls.MODEL_NAME, device="cpu")
            elapsed = time.perf_counter() - t0
            logger.info(f"Loaded '{cls.MODEL_NAME}' in {elapsed:.2f}s on CPU.")
        return cls._model

    def embed_text(self, text: str) -> list[float]:
        """
        Generate a normalized 384-dim embedding for a single string.
        """
        model = self.get_model()
        vec = model.encode(text, normalize_embeddings=True)
        return vec.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generate normalized 384-dim embeddings for a list of strings.
        """
        if not texts:
            return []
        model = self.get_model()
        vecs = model.encode(texts, normalize_embeddings=True)
        return [v.tolist() for v in vecs]
