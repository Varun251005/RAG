"""
Unit & Integration test suite for Hybrid Retrieval (Semantic Vector + BM25 Keyword).
"""

from __future__ import annotations

import pytest
import chromadb

from app.core.exceptions import UnprocessableError
from app.services.bm25_service import BM25Document, BM25Service
from app.services.local_embedding_service import LocalEmbeddingService
from app.services.vector_store_service import VectorStoreService
from app.services.retrieval_service import RAGRetrievalService
from app.models.vector_store import VectorDocument


@pytest.fixture
async def hybrid_setup():
    embed_svc = LocalEmbeddingService()
    vector_svc = VectorStoreService(default_collection="test_hybrid_voicerag")
    vector_svc._client = chromadb.EphemeralClient()
    bm25_svc = BM25Service()

    retrieval_svc = RAGRetrievalService(
        embedding_service=embed_svc,
        vector_store_service=vector_svc,
        bm25_service=bm25_svc,
        retrieval_mode="hybrid",
        vector_weight=0.7,
        keyword_weight=0.3,
    )

    sample_chunks = [
        {
            "id": "tcp_chunk_1",
            "text": "TCP uses SYN, SYN-ACK and ACK during connection establishment.",
            "document_id": "doc_tcp",
            "filename": "networking.pdf",
            "page": 1,
            "index": 0,
        },
        {
            "id": "udp_chunk_2",
            "text": "UDP is a connectionless transport protocol providing low latency communication without handshake.",
            "document_id": "doc_udp",
            "filename": "networking.pdf",
            "page": 2,
            "index": 1,
        },
        {
            "id": "python_chunk_3",
            "text": "Python is a dynamic programming language with readable syntax and rich ecosystem.",
            "document_id": "doc_py",
            "filename": "python_guide.pdf",
            "page": 1,
            "index": 0,
        },
    ]

    # Index into ChromaDB
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
        document_id="batch_hybrid",
        collection_name="test_hybrid_voicerag",
    )
    bm25_svc.add_documents(bm25_docs)

    return retrieval_svc, vector_svc, bm25_svc


@pytest.mark.asyncio
async def test_semantic_only_retrieval(hybrid_setup) -> None:
    svc, _, _ = hybrid_setup
    results = await svc.retrieve_relevant_chunks(
        question="How does reliable transport work?",
        mode="vector",
        collection_name="test_hybrid_voicerag",
    )
    assert len(results) > 0
    assert any("TCP" in r.text or "UDP" in r.text for r in results)


@pytest.mark.asyncio
async def test_keyword_only_retrieval(hybrid_setup) -> None:
    svc, _, _ = hybrid_setup
    results = await svc.retrieve_relevant_chunks(
        question="SYN-ACK",
        mode="keyword",
        collection_name="test_hybrid_voicerag",
    )
    assert len(results) > 0
    assert results[0].chunk_id == "tcp_chunk_1"
    assert "SYN-ACK" in results[0].text


@pytest.mark.asyncio
async def test_hybrid_retrieval(hybrid_setup) -> None:
    svc, _, _ = hybrid_setup
    results = await svc.retrieve_relevant_chunks(
        question="What does SYN-ACK do in TCP?",
        mode="hybrid",
        vector_weight=0.7,
        keyword_weight=0.3,
        collection_name="test_hybrid_voicerag",
    )
    assert len(results) > 0
    assert results[0].chunk_id == "tcp_chunk_1"


@pytest.mark.asyncio
async def test_exact_technical_term_query(hybrid_setup) -> None:
    svc, _, _ = hybrid_setup
    results = await svc.retrieve_relevant_chunks(
        question="What does SYN-ACK do?",
        collection_name="test_hybrid_voicerag",
    )
    assert len(results) > 0
    assert results[0].chunk_id == "tcp_chunk_1"
    assert "SYN-ACK" in results[0].text


@pytest.mark.asyncio
async def test_semantic_query(hybrid_setup) -> None:
    svc, _, _ = hybrid_setup
    results = await svc.retrieve_relevant_chunks(
        question="How does TCP establish a connection?",
        collection_name="test_hybrid_voicerag",
    )
    assert len(results) > 0
    assert results[0].chunk_id == "tcp_chunk_1"


@pytest.mark.asyncio
async def test_hybrid_query_different_rankings(hybrid_setup) -> None:
    svc, _, _ = hybrid_setup
    # Vector and BM25 produce results; hybrid fusion merges and weights scores
    vec_results = await svc.retrieve_relevant_chunks(
        question="Python Ecosystem", mode="vector", collection_name="test_hybrid_voicerag"
    )
    key_results = await svc.retrieve_relevant_chunks(
        question="Python Ecosystem", mode="keyword", collection_name="test_hybrid_voicerag"
    )
    hybrid_results = await svc.retrieve_relevant_chunks(
        question="Python Ecosystem", mode="hybrid", collection_name="test_hybrid_voicerag"
    )
    assert len(hybrid_results) > 0
    assert hybrid_results[0].chunk_id == "python_chunk_3"


@pytest.mark.asyncio
async def test_duplicate_result_merging(hybrid_setup) -> None:
    svc, _, _ = hybrid_setup
    results = await svc.retrieve_relevant_chunks(
        question="TCP SYN ACK connection",
        top_k=10,
        mode="hybrid",
        collection_name="test_hybrid_voicerag",
    )
    chunk_ids = [r.chunk_id for r in results]
    assert len(chunk_ids) == len(set(chunk_ids))  # Guarantee no duplicates


@pytest.mark.asyncio
async def test_top_k_enforcement(hybrid_setup) -> None:
    svc, _, _ = hybrid_setup
    results = await svc.retrieve_relevant_chunks(
        question="transport protocol connection",
        top_k=2,
        collection_name="test_hybrid_voicerag",
    )
    assert len(results) <= 2


@pytest.mark.asyncio
async def test_document_id_filtering(hybrid_setup) -> None:
    svc, _, _ = hybrid_setup
    # Search specifically for document_id = doc_py
    results = await svc.retrieve_relevant_chunks(
        question="TCP connection",
        document_id="doc_py",
        collection_name="test_hybrid_voicerag",
    )
    for r in results:
        assert r.document_id == "doc_py"


@pytest.mark.asyncio
async def test_cross_document_retrieval(hybrid_setup) -> None:
    svc, _, _ = hybrid_setup
    # Search without document_id filter
    results = await svc.retrieve_relevant_chunks(
        question="protocol programming",
        document_id=None,
        top_k=3,
        collection_name="test_hybrid_voicerag",
    )
    doc_ids = {r.document_id for r in results}
    assert len(doc_ids) >= 1


@pytest.mark.asyncio
async def test_empty_query_handling(hybrid_setup) -> None:
    svc, _, _ = hybrid_setup
    with pytest.raises(UnprocessableError):
        await svc.retrieve_relevant_chunks(question="   ", collection_name="test_hybrid_voicerag")


@pytest.mark.asyncio
async def test_empty_collection_handling() -> None:
    embed_svc = LocalEmbeddingService()
    vector_svc = VectorStoreService(default_collection="empty_coll")
    vector_svc._client = chromadb.EphemeralClient()
    bm25_svc = BM25Service()

    svc = RAGRetrievalService(
        embedding_service=embed_svc,
        vector_store_service=vector_svc,
        bm25_service=bm25_svc,
    )
    results = await svc.retrieve_relevant_chunks(
        question="Anything here?", collection_name="empty_coll"
    )
    assert results == []


@pytest.mark.asyncio
async def test_bm25_consistency_after_ingestion(hybrid_setup) -> None:
    _, _, bm25_svc = hybrid_setup
    initial_count = bm25_svc.get_document_count()

    new_doc = BM25Document(
        chunk_id="new_chunk_100",
        text="Rust is a systems programming language focusing on memory safety.",
        document_id="doc_rust",
        source_filename="rust.pdf",
        page_number=1,
        chunk_index=0,
    )
    bm25_svc.add_documents([new_doc])
    assert bm25_svc.get_document_count() == initial_count + 1

    search_res = bm25_svc.search(query="memory safety")
    assert len(search_res) > 0
    assert search_res[0][0].chunk_id == "new_chunk_100"


@pytest.mark.asyncio
async def test_bm25_consistency_after_deletion(hybrid_setup) -> None:
    _, _, bm25_svc = hybrid_setup
    bm25_svc.delete_document("doc_tcp")
    assert len(bm25_svc.get_documents_by_doc_id("doc_tcp")) == 0
    search_res = bm25_svc.search(query="SYN-ACK")
    assert len(search_res) == 0


@pytest.mark.asyncio
async def test_reprocessing_document_no_duplicates(hybrid_setup) -> None:
    _, _, bm25_svc = hybrid_setup
    initial_count = bm25_svc.get_document_count()

    dup_doc = BM25Document(
        chunk_id="tcp_chunk_1",
        text="TCP uses SYN, SYN-ACK and ACK during connection establishment updated.",
        document_id="doc_tcp",
        source_filename="networking.pdf",
        page_number=1,
        chunk_index=0,
    )
    bm25_svc.add_documents([dup_doc])
    # Count must remain identical (no duplicate chunk entries created)
    assert bm25_svc.get_document_count() == initial_count
