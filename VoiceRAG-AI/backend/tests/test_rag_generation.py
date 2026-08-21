"""
Integration tests for RAG LLM generation using local Qwen model (qwen2.5:0.5b) via Ollama.
"""

from __future__ import annotations

import json
import time
import pytest
import chromadb
from pathlib import Path

from app.services.local_embedding_service import LocalEmbeddingService
from app.services.vector_store_service import VectorStoreService
from app.services.retrieval_service import RAGRetrievalService
from app.services.llm_service import OllamaLLMService
from app.models.vector_store import VectorDocument


@pytest.mark.asyncio
async def test_full_rag_llm_pipeline() -> None:
    embed_svc = LocalEmbeddingService()
    vector_svc = VectorStoreService(default_collection="test_rag_llm_pipeline")
    vector_svc._client = chromadb.EphemeralClient()

    retrieval_svc = RAGRetrievalService(
        embedding_service=embed_svc,
        vector_store_service=vector_svc,
    )
    llm_svc = OllamaLLMService(model_name="qwen2.5:0.5b")

    sample_texts = [
        "Python is a programming language commonly used for software development and artificial intelligence.",
        "Machine learning allows systems to learn patterns from data.",
        "FastAPI is a Python framework for building high-performance web APIs.",
    ]
    doc_ids = ["doc_py_1", "doc_ml_2", "doc_api_3"]
    filenames = ["python_guide.pdf", "ml_book.pdf", "fastapi_manual.pdf"]

    embeddings = embed_svc.embed_batch(sample_texts)
    vec_docs = [
        VectorDocument(
            id=f"chunk_{idx}",
            embedding=embeddings[idx],
            text=sample_texts[idx],
            metadata={
                "document_id": doc_ids[idx],
                "source_filename": filenames[idx],
                "page_number": idx + 1,
                "chunk_index": 0,
            },
        )
        for idx in range(3)
    ]

    await vector_svc.upsert_documents(
        documents=vec_docs,
        document_id="batch_llm_pipeline_docs",
        collection_name="test_rag_llm_pipeline",
    )

    results_report = {}

    # Test 1: In-context question
    q1 = "What is Python used for?"
    t0 = time.perf_counter()
    chunks1 = await retrieval_svc.retrieve_relevant_chunks(
        question=q1,
        top_k=2,
        collection_name="test_rag_llm_pipeline",
    )
    ans1 = await llm_svc.generate_rag_answer(question=q1, retrieved_chunks=chunks1)
    t1 = time.perf_counter()

    results_report["test_1_in_context"] = {
        "question": q1,
        "answer": ans1.answer,
        "sources": [s.model_dump() for s in ans1.sources],
        "latency_ms": ans1.generation_time_ms,
        "total_elapsed_ms": (t1 - t0) * 1000.0,
    }

    assert "software development" in ans1.answer.lower() or "artificial intelligence" in ans1.answer.lower() or "python" in ans1.answer.lower()
    assert len(ans1.sources) > 0

    # Test 2: Out-of-context question
    q2 = "What is the capital of France?"
    chunks2 = await retrieval_svc.retrieve_relevant_chunks(
        question=q2,
        top_k=2,
        score_threshold=0.75,
        collection_name="test_rag_llm_pipeline",
    )
    ans2 = await llm_svc.generate_rag_answer(question=q2, retrieved_chunks=chunks2)

    results_report["test_2_out_of_context"] = {
        "question": q2,
        "answer": ans2.answer,
        "sources": [s.model_dump() for s in ans2.sources],
    }

    assert "not available" in ans2.answer.lower()

    Path("rag_llm_test_report.json").write_text(json.dumps(results_report, indent=2))
