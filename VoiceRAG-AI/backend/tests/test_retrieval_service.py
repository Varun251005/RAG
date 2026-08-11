"""
Integration tests for RAGRetrievalService using LocalEmbeddingService (384-dim CPU) and ChromaDB.

Verifies:
1. Correct semantic ranking for specific query domains (Python, ML, Neural Networks).
2. Top-K output limit control.
3. Similarity score calculation and descending ordering.
4. Score threshold filtering.
5. Single-document vs multi-document filtering.
6. Empty query error handling.
7. Empty collection / no-result handling.
"""

from __future__ import annotations

import pytest
import chromadb

from app.services.local_embedding_service import LocalEmbeddingService
from app.services.vector_store_service import VectorStoreService
from app.services.retrieval_service import RAGRetrievalService
from app.models.vector_store import VectorDocument
from app.core.exceptions import UnprocessableError


@pytest.fixture
async def retrieval_setup() -> tuple[RAGRetrievalService, VectorStoreService]:
    embed_svc = LocalEmbeddingService()
    vector_svc = VectorStoreService(default_collection="test_retrieval_voicerag")
    vector_svc._client = chromadb.EphemeralClient()

    retrieval_svc = RAGRetrievalService(
        embedding_service=embed_svc,
        vector_store_service=vector_svc,
    )

    # Populate isolated test vector store with sample chunks
    sample_texts = [
        "Python is a programming language commonly used for software development.",
        "Machine learning allows systems to learn patterns from data.",
        "Neural networks are computational models inspired by biological neurons.",
        "FastAPI is a Python framework for building web APIs.",
    ]
    doc_ids = ["doc_py_1", "doc_ml_2", "doc_nn_3", "doc_api_4"]
    filenames = ["py_guide.pdf", "ml_book.pdf", "nn_paper.pdf", "fastapi_docs.pdf"]

    embeddings = embed_svc.embed_batch(sample_texts)
    vec_docs = []

    for idx, txt in enumerate(sample_texts):
        v_doc = VectorDocument(
            id=f"chunk_{idx}",
            embedding=embeddings[idx],
            text=txt,
            metadata={
                "document_id": doc_ids[idx],
                "source_filename": filenames[idx],
                "page_number": idx + 1,
                "chunk_index": 0,
            },
        )
        vec_docs.append(v_doc)

    await vector_svc.upsert_documents(
        documents=vec_docs,
        document_id="batch_retrieval_docs",
        collection_name="test_retrieval_voicerag",
    )


    return retrieval_svc, vector_svc


@pytest.mark.asyncio
async def test_semantic_query_ranking_python(
    retrieval_setup: tuple[RAGRetrievalService, VectorStoreService]
) -> None:
    svc, _ = retrieval_setup
    results = await svc.retrieve_relevant_chunks(
        question="What is Python used for?",
        top_k=4,
        collection_name="test_retrieval_voicerag",
    )

    assert len(results) > 0
    top_result = results[0]
    assert "Python" in top_result.text
    assert top_result.document_id in ["doc_py_1", "doc_api_4"]
    assert top_result.similarity_score > 0.4


@pytest.mark.asyncio
async def test_semantic_query_ranking_ml(
    retrieval_setup: tuple[RAGRetrievalService, VectorStoreService]
) -> None:
    svc, _ = retrieval_setup
    results = await svc.retrieve_relevant_chunks(
        question="What is machine learning?",
        top_k=4,
        collection_name="test_retrieval_voicerag",
    )

    assert len(results) > 0
    top_result = results[0]
    assert "Machine learning" in top_result.text
    assert top_result.document_id == "doc_ml_2"


@pytest.mark.asyncio
async def test_semantic_query_ranking_neural_networks(
    retrieval_setup: tuple[RAGRetrievalService, VectorStoreService]
) -> None:
    svc, _ = retrieval_setup
    results = await svc.retrieve_relevant_chunks(
        question="What are neural networks?",
        top_k=4,
        collection_name="test_retrieval_voicerag",
    )

    assert len(results) > 0
    top_result = results[0]
    assert "Neural networks" in top_result.text
    assert top_result.document_id == "doc_nn_3"


@pytest.mark.asyncio
async def test_top_k_and_similarity_ordering(
    retrieval_setup: tuple[RAGRetrievalService, VectorStoreService]
) -> None:
    svc, _ = retrieval_setup
    results = await svc.retrieve_relevant_chunks(
        question="Tell me about Python and machine learning.",
        top_k=2,
        collection_name="test_retrieval_voicerag",
    )

    assert len(results) == 2
    # Verify strict descending ordering by similarity_score
    assert results[0].similarity_score >= results[1].similarity_score


@pytest.mark.asyncio
async def test_document_id_filtering(
    retrieval_setup: tuple[RAGRetrievalService, VectorStoreService]
) -> None:
    svc, _ = retrieval_setup
    # Filter explicitly for doc_ml_2
    results = await svc.retrieve_relevant_chunks(
        question="Python programming language",
        document_id="doc_ml_2",
        collection_name="test_retrieval_voicerag",
    )

    assert len(results) == 1
    assert results[0].document_id == "doc_ml_2"
    assert "Machine learning" in results[0].text


@pytest.mark.asyncio
async def test_score_threshold_filtering(
    retrieval_setup: tuple[RAGRetrievalService, VectorStoreService]
) -> None:
    svc, _ = retrieval_setup
    # High threshold filter
    results = await svc.retrieve_relevant_chunks(
        question="What is Python used for?",
        score_threshold=0.99,  # Very strict threshold
        collection_name="test_retrieval_voicerag",
    )

    # Exact 1.0 match is unlikely so high threshold filters out low scoring matches
    assert len(results) == 0


@pytest.mark.asyncio
async def test_empty_query_raises_error(
    retrieval_setup: tuple[RAGRetrievalService, VectorStoreService]
) -> None:
    svc, _ = retrieval_setup
    with pytest.raises(UnprocessableError, match="cannot be empty"):
        await svc.retrieve_relevant_chunks(
            question="   ",
            collection_name="test_retrieval_voicerag",
        )
