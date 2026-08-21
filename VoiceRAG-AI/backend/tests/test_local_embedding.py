"""
Unit tests for LocalEmbeddingService using sentence-transformers/all-MiniLM-L6-v2 on CPU.
"""

from app.services.local_embedding_service import LocalEmbeddingService


def test_local_embedding_service_cpu_dimension() -> None:
    service = LocalEmbeddingService()
    text = "Python is a programming language."
    vec = service.embed_text(text)

    assert isinstance(vec, list)
    assert len(vec) == 384
    assert service.get_model().device.type == "cpu"


def test_local_embedding_batch() -> None:
    service = LocalEmbeddingService()
    texts = ["First text", "Second text"]
    vecs = service.embed_batch(texts)

    assert len(vecs) == 2
    assert len(vecs[0]) == 384
    assert len(vecs[1]) == 384
