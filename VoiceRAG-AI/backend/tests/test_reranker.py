"""
Unit and Integration tests for CrossEncoder CPU Reranker Layer.
"""

from __future__ import annotations

import time
import pytest
import chromadb

from app.core.exceptions import UnprocessableError
from app.models.vector_store import VectorDocument
from app.services.bm25_service import BM25Document, BM25Service
from app.services.local_embedding_service import LocalEmbeddingService
from app.services.reranker_service import RerankerService
from app.services.retrieval_service import RAGRetrievalService, RetrievedChunk
from app.services.vector_store_service import VectorStoreService


@pytest.fixture
def sample_candidates() -> list[RetrievedChunk]:
    return [
        RetrievedChunk(
            chunk_id="chunk_1",
            text="The weather in Paris is sunny today.",
            document_id="doc_weather",
            source_filename="weather.pdf",
            page_number=1,
            chunk_index=0,
            distance=0.2,
            similarity_score=0.8,
        ),
        RetrievedChunk(
            chunk_id="chunk_2",
            text="Python is a high-level programming language used in machine learning.",
            document_id="doc_py",
            source_filename="python.pdf",
            page_number=1,
            chunk_index=0,
            distance=0.1,
            similarity_score=0.9,
        ),
        RetrievedChunk(
            chunk_id="chunk_3",
            text="FastAPI is a modern web framework for building APIs with Python 3.8+.",
            document_id="doc_fastapi",
            source_filename="fastapi.pdf",
            page_number=2,
            chunk_index=1,
            distance=0.15,
            similarity_score=0.85,
        ),
    ]


@pytest.fixture
async def reranker_setup():
    embed_svc = LocalEmbeddingService()
    vector_svc = VectorStoreService(default_collection="test_reranker_voicerag")
    vector_svc._client = chromadb.EphemeralClient()
    bm25_svc = BM25Service()
    reranker_svc = RerankerService(model_name="cross-encoder/ms-marco-MiniLM-L-6-v2", device="cpu")

    retrieval_svc = RAGRetrievalService(
        embedding_service=embed_svc,
        vector_store_service=vector_svc,
        bm25_service=bm25_svc,
        reranker_service=reranker_svc,
        reranker_enabled=True,
        candidate_k=15,
    )

    sample_chunks = [
        {
            "id": f"chunk_{i:02d}",
            "text": f"General computer document paragraph {i} talking about software engineering.",
            "document_id": "doc_general",
            "filename": "general.pdf",
            "page": i + 1,
            "index": i,
        }
        for i in range(12)
    ]
    # Specific targeted chunks
    sample_chunks.extend([
        {
            "id": "target_chunk_tcp",
            "text": "Transmission Control Protocol (TCP) uses a three-way handshake involving SYN, SYN-ACK, and ACK packets.",
            "document_id": "doc_tcp",
            "filename": "tcp.pdf",
            "page": 5,
            "index": 2,
        },
        {
            "id": "target_chunk_udp",
            "text": "User Datagram Protocol (UDP) is connectionless and sends datagrams without establishing a handshake.",
            "document_id": "doc_udp",
            "filename": "udp.pdf",
            "page": 1,
            "index": 0,
        },
    ])

    texts = [c["text"] for c in sample_chunks]
    embeddings = embed_svc.embed_batch(texts)
    v_docs = []
    bm25_docs = []

    for idx, c in enumerate(sample_chunks):
        v_docs.append(
            VectorDocument(
                id=c["id"],
                embedding=embeddings[idx],
                text=c["text"],
                metadata={
                    "document_id": c["document_id"],
                    "source_filename": c["filename"],
                    "page_number": c["page"],
                    "chunk_index": c["index"],
                },
            )
        )
        bm25_docs.append(
            BM25Document(
                chunk_id=c["id"],
                text=c["text"],
                document_id=c["document_id"],
                source_filename=c["filename"],
                page_number=c["page"],
                chunk_index=c["index"],
            )
        )

    await vector_svc.upsert_documents(
        documents=v_docs,
        document_id="batch_reranker",
        collection_name="test_reranker_voicerag",
    )
    bm25_svc.add_documents(bm25_docs)

    return retrieval_svc, reranker_svc


def test_reranker_service_model_loading_and_cpu_execution() -> None:
    svc = RerankerService(model_name="cross-encoder/ms-marco-MiniLM-L-6-v2", device="cpu")
    model = svc._get_model()
    assert model is not None
    assert svc.device == "cpu"


def test_reranker_accepts_candidates_and_ranks(sample_candidates: list[RetrievedChunk]) -> None:
    svc = RerankerService(model_name="cross-encoder/ms-marco-MiniLM-L-6-v2", device="cpu")
    svc._get_model()  # Ensure model weights are loaded into memory first

    start_time = time.time()
    results = svc.rerank(
        question="What programming language is used for Python machine learning?",
        candidates=sample_candidates,
        top_k=2,
    )
    elapsed_ms = (time.time() - start_time) * 1000.0

    assert len(results) == 2
    # The top reranked result should be the Python chunk
    assert results[0].chunk_id == "chunk_2"
    assert "Python" in results[0].text
    assert results[0].reranker_score is not None
    assert elapsed_ms < 1000.0  # CPU inference must be fast (<1s)


def test_reranker_metadata_preservation(sample_candidates: list[RetrievedChunk]) -> None:
    svc = RerankerService(model_name="cross-encoder/ms-marco-MiniLM-L-6-v2", device="cpu")
    results = svc.rerank(
        question="What is FastAPI?",
        candidates=sample_candidates,
        top_k=1,
    )

    top = results[0]
    assert top.chunk_id == "chunk_3"
    assert top.document_id == "doc_fastapi"
    assert top.source_filename == "fastapi.pdf"
    assert top.page_number == 2
    assert top.chunk_index == 1
    assert top.distance == 0.15
    assert top.similarity_score == 0.85
    assert top.reranker_score is not None


def test_reranker_empty_candidates() -> None:
    svc = RerankerService(model_name="cross-encoder/ms-marco-MiniLM-L-6-v2", device="cpu")
    res = svc.rerank(question="Anything?", candidates=[], top_k=5)
    assert res == []


def test_reranker_empty_question(sample_candidates: list[RetrievedChunk]) -> None:
    svc = RerankerService(model_name="cross-encoder/ms-marco-MiniLM-L-6-v2", device="cpu")
    res = svc.rerank(question="   ", candidates=sample_candidates, top_k=5)
    assert res == []


@pytest.mark.asyncio
async def test_retrieval_with_reranker_enabled(reranker_setup) -> None:
    retrieval_svc, _ = reranker_setup
    results = await retrieval_svc.retrieve_relevant_chunks(
        question="How does TCP establish a connection with SYN and SYN-ACK?",
        top_k=5,
        reranker_enabled=True,
        candidate_k=15,
        collection_name="test_reranker_voicerag",
    )

    assert len(results) > 0
    assert len(results) <= 5
    assert results[0].chunk_id == "target_chunk_tcp"
    assert results[0].reranker_score is not None


@pytest.mark.asyncio
async def test_retrieval_with_reranker_disabled(reranker_setup) -> None:
    retrieval_svc, _ = reranker_setup
    results = await retrieval_svc.retrieve_relevant_chunks(
        question="How does TCP establish a connection with SYN and SYN-ACK?",
        top_k=5,
        reranker_enabled=False,
        collection_name="test_reranker_voicerag",
    )

    assert len(results) > 0
    assert len(results) <= 5
    # When disabled, reranker_score should remain None
    assert results[0].reranker_score is None


@pytest.mark.asyncio
async def test_reranker_document_id_filtering(reranker_setup) -> None:
    retrieval_svc, _ = reranker_setup
    results = await retrieval_svc.retrieve_relevant_chunks(
        question="TCP handshake SYN ACK",
        document_id="doc_udp",
        top_k=5,
        reranker_enabled=True,
        collection_name="test_reranker_voicerag",
    )

    for r in results:
        assert r.document_id == "doc_udp"


@pytest.mark.asyncio
async def test_no_duplicate_chunks_introduced(reranker_setup) -> None:
    retrieval_svc, _ = reranker_setup
    results = await retrieval_svc.retrieve_relevant_chunks(
        question="software engineering computer protocol",
        top_k=10,
        reranker_enabled=True,
        candidate_k=15,
        collection_name="test_reranker_voicerag",
    )

    chunk_ids = [r.chunk_id for r in results]
    assert len(chunk_ids) == len(set(chunk_ids))
