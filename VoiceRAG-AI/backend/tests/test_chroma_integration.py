"""
Integration test connecting LocalEmbeddingService (all-MiniLM-L6-v2, 384-dim CPU)
with ChromaDB vector store.

Verifies:
1. Embedding generation via LocalEmbeddingService
2. Upsert of document chunks + metadata into ChromaDB
3. Cosine similarity search returning the Python-related chunk first for query "What is Python used for?"
4. Metadata retrieval by ID
5. Document deletion and collection count tracking
"""

from __future__ import annotations

import pytest
import chromadb

from app.services.local_embedding_service import LocalEmbeddingService
from app.services.vector_store_service import VectorStoreService
from app.models.vector_store import VectorDocument


@pytest.fixture
async def chroma_local_setup() -> tuple[VectorStoreService, LocalEmbeddingService]:
    """Fixture providing VectorStoreService with an in-memory Chroma client and LocalEmbeddingService."""
    embedding_svc = LocalEmbeddingService()
    vector_svc = VectorStoreService(default_collection="test_voicerag")
    vector_svc._client = chromadb.EphemeralClient()
    return vector_svc, embedding_svc


@pytest.mark.asyncio
async def test_chroma_local_embedding_integration(
    chroma_local_setup: tuple[VectorStoreService, LocalEmbeddingService]
) -> None:
    vector_svc, embedding_svc = chroma_local_setup

    texts = [
        "Python is a programming language used for software development.",
        "Machine learning allows computers to learn patterns from data.",
        "Neural networks are computational models inspired by biological neurons.",
    ]
    doc_ids = ["doc_py_01", "doc_ml_02", "doc_nn_03"]
    chunk_ids = ["chunk_py_0", "chunk_ml_0", "chunk_nn_0"]
    filenames = ["python_guide.pdf", "ml_intro.pdf", "nn_basics.pdf"]

    # 1. Generate 384-dim embeddings using local CPU model
    embeddings = embedding_svc.embed_batch(texts)
    assert len(embeddings) == 3
    assert all(len(emb) == 384 for emb in embeddings)

    # 2. Build VectorDocuments with complete metadata
    vec_docs = []
    for i in range(3):
        vec_doc = VectorDocument(
            id=chunk_ids[i],
            embedding=embeddings[i],
            text=texts[i],
            metadata={
                "document_id": doc_ids[i],
                "source_filename": filenames[i],
                "page_number": 1,
                "chunk_index": 0,
            },
        )
        vec_docs.append(vec_doc)

    # 3. Upsert documents into ChromaDB
    upsert_res = await vector_svc.upsert_documents(vec_docs, document_id="batch_01")
    assert upsert_res.upserted == 3

    # 4. Check collection count
    col_info = await vector_svc.collection_info()
    assert col_info.count == 3

    # 5. Execute query similarity search
    query_text = "What is Python used for?"
    query_embedding = embedding_svc.embed_text(query_text)
    assert len(query_embedding) == 384

    search_res = await vector_svc.search(
        query_vector=query_embedding,
        query_text=query_text,
        n_results=3,
    )

    assert len(search_res.results) == 3
    top_result = search_res.results[0]

    # Verify top result is Python chunk
    assert top_result.id == "chunk_py_0"
    assert "Python" in top_result.text
    assert top_result.metadata["document_id"] == "doc_py_01"
    assert top_result.metadata["source_filename"] == "python_guide.pdf"

    # 6. Verify metadata retrieval by ID
    fetched_rows = await vector_svc.get_by_ids(["chunk_py_0"])
    assert len(fetched_rows) == 1
    assert fetched_rows[0]["id"] == "chunk_py_0"
    assert fetched_rows[0]["metadata"]["source_filename"] == "python_guide.pdf"

    # 7. Verify document deletion
    del_res = await vector_svc.delete_document("doc_py_01")
    assert del_res.deleted == 1

    col_info_after = await vector_svc.collection_info()
    assert col_info_after.count == 2
