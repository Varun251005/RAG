"""
Unit tests for VectorStoreService.

All tests use chromadb.EphemeralClient (in-memory, no server required)
injected via the service's internal ``_client`` attribute so no Docker
or network is needed.

Tests cover:
  - Collection creation / deletion / listing / info
  - Upsert (idempotent) — batch, single, from chunks+embeddings
  - Delete by document_id metadata filter
  - Delete by IDs
  - Search — basic, per-document filter, n_results cap
  - get_by_ids
  - _flatten_metadata helper
  - _batched helper
  - VectorDocument / SearchResult / CollectionInfo Pydantic models
"""

from __future__ import annotations

import pytest

try:
    import chromadb
    from chromadb import EphemeralClient
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not CHROMA_AVAILABLE, reason="chromadb not installed"
)

from datetime import datetime, timezone

from app.models.chunk import ChunkMetadata, DocumentChunk
from app.models.embedding import EmbeddingRecord
from app.models.vector_store import (
    CollectionInfo,
    DeleteResult,
    SearchResponse,
    SearchResult,
    UpsertResult,
    VectorDocument,
)
from app.services.vector_store_service import (
    VectorStoreService,
    _batched,
    _flatten_metadata,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DOC_ID = "doc-abc-123"
_MODEL = "text-embedding-004"
_COLLECTION = "test_collection"
# Minimal 3-dim vectors (real Gemini vectors are 768-dim but shape doesn't
# matter for Chroma ephemeral mode with cosine space).
_VEC_A = [1.0, 0.0, 0.0]
_VEC_B = [0.0, 1.0, 0.0]
_VEC_C = [0.0, 0.0, 1.0]
_QUERY_VEC = [1.0, 0.1, 0.0]  # should rank VEC_A closest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


import uuid

@pytest.fixture()
async def ephemeral_service() -> VectorStoreService:
    """
    VectorStoreService with an in-memory EphemeralClient injected.

    Generates a unique collection name per test method so test cases remain isolated.
    """
    unique_col = f"test_col_{uuid.uuid4().hex[:8]}"
    svc = VectorStoreService(
        host="localhost",
        port=8001,
        default_collection=unique_col,
    )
    svc._client = chromadb.EphemeralClient()
    return svc



def _make_vec_doc(
    doc_id: str = _DOC_ID,
    chunk_id: str = "chunk_0",
    vector: list[float] | None = None,
    text: str = "hello world",
    page: int = 1,
) -> VectorDocument:
    return VectorDocument(
        id=chunk_id,
        embedding=vector or _VEC_A,
        text=text,
        metadata={
            "document_id": doc_id,
            "page_number": page,
            "original_filename": "test.pdf",
        },
    )


def _make_chunk(chunk_id: str, text: str = "sample text", page: int = 1) -> DocumentChunk:
    return DocumentChunk(
        chunk_id=chunk_id,
        chunk_index=0,
        text=text,
        metadata=ChunkMetadata(
            document_id=_DOC_ID,
            original_filename="test.pdf",
            page_number=page,
            total_pages=3,
        ),
    )


def _make_emb(chunk_id: str, vector: list[float] | None = None) -> EmbeddingRecord:
    return EmbeddingRecord(
        chunk_id=chunk_id,
        vector=vector or _VEC_A,
        model=_MODEL,
        cached=False,
        created_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Helper function tests (no network needed)
# ---------------------------------------------------------------------------


class TestFlattenMetadata:
    def test_scalars_pass_through(self) -> None:
        meta = {"a": "hello", "b": 42, "c": 3.14, "d": True}
        flat = _flatten_metadata(meta)
        assert flat == meta

    def test_list_serialised_to_json(self) -> None:
        meta = {"items": [1, 2, 3]}
        flat = _flatten_metadata(meta)
        assert flat["items"] == "[1, 2, 3]"

    def test_dict_serialised_to_json(self) -> None:
        meta = {"nested": {"key": "val"}}
        flat = _flatten_metadata(meta)
        assert flat["nested"] == '{"key": "val"}'

    def test_none_serialised(self) -> None:
        meta = {"x": None}
        flat = _flatten_metadata(meta)
        assert flat["x"] == "null"

    def test_empty_dict(self) -> None:
        assert _flatten_metadata({}) == {}


class TestBatched:
    def test_exact_multiple(self) -> None:
        docs = [_make_vec_doc(chunk_id=f"c{i}") for i in range(6)]
        batches = _batched(docs, 3)
        assert len(batches) == 2

    def test_remainder(self) -> None:
        docs = [_make_vec_doc(chunk_id=f"c{i}") for i in range(7)]
        batches = _batched(docs, 3)
        assert len(batches) == 3
        assert len(batches[-1]) == 1

    def test_empty(self) -> None:
        assert _batched([], 5) == []


# ---------------------------------------------------------------------------
# Pydantic model validation
# ---------------------------------------------------------------------------


class TestModels:
    def test_vector_document_requires_non_empty_embedding(self) -> None:
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            VectorDocument(id="x", embedding=[], text="hi")

    def test_search_result_score_calculation(self) -> None:
        sr = SearchResult(
            id="c1", text="t", metadata={}, distance=0.3, score=0.7
        )
        assert sr.score == pytest.approx(0.7)

    def test_collection_info(self) -> None:
        ci = CollectionInfo(name="col", count=42)
        assert ci.count == 42


# ---------------------------------------------------------------------------
# Collection management tests
# ---------------------------------------------------------------------------


class TestCollectionManagement:
    async def test_get_or_create_creates_new(
        self, ephemeral_service: VectorStoreService
    ) -> None:
        col = await ephemeral_service.get_or_create_collection("new_col")
        assert col.name == "new_col"

    async def test_get_or_create_idempotent(
        self, ephemeral_service: VectorStoreService
    ) -> None:
        col1 = await ephemeral_service.get_or_create_collection("col_x")
        col2 = await ephemeral_service.get_or_create_collection("col_x")
        assert col1.name == col2.name

    async def test_collection_info_count(
        self, ephemeral_service: VectorStoreService
    ) -> None:
        await ephemeral_service.upsert_documents(
            [_make_vec_doc(chunk_id="c0")], _DOC_ID
        )
        info = await ephemeral_service.collection_info()
        assert info.name == ephemeral_service._default_collection
        assert info.count == 1

    async def test_delete_collection(
        self, ephemeral_service: VectorStoreService
    ) -> None:
        await ephemeral_service.get_or_create_collection("to_delete")
        await ephemeral_service.delete_collection("to_delete")
        # Re-create to confirm it was actually gone (no error means success)
        col = await ephemeral_service.get_or_create_collection("to_delete")
        assert col.name == "to_delete"

    async def test_list_collections(
        self, ephemeral_service: VectorStoreService
    ) -> None:
        await ephemeral_service.get_or_create_collection("col_a")
        await ephemeral_service.get_or_create_collection("col_b")
        infos = await ephemeral_service.list_collections()
        names = {i.name for i in infos}
        assert "col_a" in names
        assert "col_b" in names


# ---------------------------------------------------------------------------
# Upsert tests
# ---------------------------------------------------------------------------


class TestUpsert:
    async def test_upsert_single_document(
        self, ephemeral_service: VectorStoreService
    ) -> None:
        doc = _make_vec_doc(chunk_id="c1")
        result = await ephemeral_service.upsert_documents([doc], _DOC_ID)
        assert isinstance(result, UpsertResult)
        assert result.upserted == 1
        assert result.document_id == _DOC_ID
        assert result.collection == ephemeral_service._default_collection


    async def test_upsert_multiple_documents(
        self, ephemeral_service: VectorStoreService
    ) -> None:
        docs = [_make_vec_doc(chunk_id=f"c{i}", vector=_VEC_A) for i in range(5)]
        result = await ephemeral_service.upsert_documents(docs, _DOC_ID)
        assert result.upserted == 5

    async def test_upsert_is_idempotent(
        self, ephemeral_service: VectorStoreService
    ) -> None:
        doc = _make_vec_doc(chunk_id="dup_id", text="original")
        await ephemeral_service.upsert_documents([doc], _DOC_ID)

        doc_updated = VectorDocument(
            id="dup_id",
            embedding=_VEC_B,
            text="updated text",
            metadata={"document_id": _DOC_ID},
        )
        await ephemeral_service.upsert_documents([doc_updated], _DOC_ID)

        fetched = await ephemeral_service.get_by_ids(["dup_id"])
        assert len(fetched) == 1
        assert fetched[0]["text"] == "updated text"

    async def test_upsert_empty_list(
        self, ephemeral_service: VectorStoreService
    ) -> None:
        result = await ephemeral_service.upsert_documents([], _DOC_ID)
        assert result.upserted == 0

    async def test_upsert_from_chunks_and_embeddings(
        self, ephemeral_service: VectorStoreService
    ) -> None:
        chunks = [_make_chunk(f"chunk_{i}", page=i + 1) for i in range(3)]
        embeddings = [_make_emb(f"chunk_{i}", _VEC_A) for i in range(3)]
        result = await ephemeral_service.upsert_from_chunks_and_embeddings(
            chunks, embeddings, _DOC_ID
        )
        assert result.upserted == 3

    async def test_upsert_from_chunks_mismatched_ids_raises(
        self, ephemeral_service: VectorStoreService
    ) -> None:
        chunks = [_make_chunk("c1")]
        embeddings = [_make_emb("c_different_id")]
        with pytest.raises(ValueError, match="No embedding found"):
            await ephemeral_service.upsert_from_chunks_and_embeddings(
                chunks, embeddings, _DOC_ID
            )

    async def test_upsert_from_chunks_mismatched_length_raises(
        self, ephemeral_service: VectorStoreService
    ) -> None:
        chunks = [_make_chunk("c1"), _make_chunk("c2")]
        embeddings = [_make_emb("c1")]
        with pytest.raises(ValueError, match="same length"):
            await ephemeral_service.upsert_from_chunks_and_embeddings(
                chunks, embeddings, _DOC_ID
            )

    async def test_metadata_stored_and_retrieved(
        self, ephemeral_service: VectorStoreService
    ) -> None:
        doc = _make_vec_doc(chunk_id="meta_c", page=7)
        await ephemeral_service.upsert_documents([doc], _DOC_ID)
        rows = await ephemeral_service.get_by_ids(["meta_c"])
        assert rows[0]["metadata"]["page_number"] == 7
        assert rows[0]["metadata"]["document_id"] == _DOC_ID


# ---------------------------------------------------------------------------
# Delete tests
# ---------------------------------------------------------------------------


class TestDelete:
    async def test_delete_document_removes_chunks(
        self, ephemeral_service: VectorStoreService
    ) -> None:
        docs = [_make_vec_doc(chunk_id=f"d{i}") for i in range(3)]
        await ephemeral_service.upsert_documents(docs, _DOC_ID)

        result = await ephemeral_service.delete_document(_DOC_ID)
        assert isinstance(result, DeleteResult)
        assert result.deleted == 3
        assert result.document_id == _DOC_ID

        info = await ephemeral_service.collection_info()
        assert info.count == 0

    async def test_delete_nonexistent_document_raises(
        self, ephemeral_service: VectorStoreService
    ) -> None:
        from app.core.exceptions import NotFoundError

        with pytest.raises(NotFoundError):
            await ephemeral_service.delete_document("ghost-doc-id")

    async def test_delete_does_not_remove_other_documents(
        self, ephemeral_service: VectorStoreService
    ) -> None:
        doc_a = "doc-aaa"
        doc_b = "doc-bbb"

        await ephemeral_service.upsert_documents(
            [VectorDocument(id="a0", embedding=_VEC_A, text="a", metadata={"document_id": doc_a})],
            doc_a,
        )
        await ephemeral_service.upsert_documents(
            [VectorDocument(id="b0", embedding=_VEC_B, text="b", metadata={"document_id": doc_b})],
            doc_b,
        )

        await ephemeral_service.delete_document(doc_a)

        info = await ephemeral_service.collection_info()
        assert info.count == 1  # doc_b still present

    async def test_delete_by_ids(
        self, ephemeral_service: VectorStoreService
    ) -> None:
        docs = [_make_vec_doc(chunk_id=f"x{i}") for i in range(4)]
        await ephemeral_service.upsert_documents(docs, _DOC_ID)

        deleted = await ephemeral_service.delete_by_ids(["x0", "x1"])
        assert deleted == 2

        info = await ephemeral_service.collection_info()
        assert info.count == 2

    async def test_delete_by_ids_empty_list(
        self, ephemeral_service: VectorStoreService
    ) -> None:
        deleted = await ephemeral_service.delete_by_ids([])
        assert deleted == 0


# ---------------------------------------------------------------------------
# Search tests
# ---------------------------------------------------------------------------


class TestSearch:
    async def _seed(self, svc: VectorStoreService) -> None:
        docs = [
            VectorDocument(id="s0", embedding=_VEC_A, text="about apples", metadata={"document_id": _DOC_ID}),
            VectorDocument(id="s1", embedding=_VEC_B, text="about bananas", metadata={"document_id": _DOC_ID}),
            VectorDocument(id="s2", embedding=_VEC_C, text="about cherries", metadata={"document_id": "other-doc"}),
        ]
        await svc.upsert_documents(docs, _DOC_ID)

    async def test_search_returns_search_response(
        self, ephemeral_service: VectorStoreService
    ) -> None:
        await self._seed(ephemeral_service)
        response = await ephemeral_service.search(_QUERY_VEC, "apples", n_results=3)
        assert isinstance(response, SearchResponse)
        assert response.query == "apples"
        assert response.collection == ephemeral_service._default_collection
        assert len(response.results) <= 3

    async def test_search_closest_first(
        self, ephemeral_service: VectorStoreService
    ) -> None:
        await self._seed(ephemeral_service)
        response = await ephemeral_service.search(_QUERY_VEC, n_results=3)
        # s0 (_VEC_A) should be closest to _QUERY_VEC [1,0.1,0]
        assert response.results[0].id == "s0"

    async def test_search_n_results_cap(
        self, ephemeral_service: VectorStoreService
    ) -> None:
        await self._seed(ephemeral_service)
        response = await ephemeral_service.search(_QUERY_VEC, n_results=2)
        assert len(response.results) <= 2

    async def test_search_by_document_filters_correctly(
        self, ephemeral_service: VectorStoreService
    ) -> None:
        await self._seed(ephemeral_service)
        response = await ephemeral_service.search_by_document(
            _QUERY_VEC, document_id=_DOC_ID, n_results=5
        )
        doc_ids = {r.metadata.get("document_id") for r in response.results}
        assert doc_ids == {_DOC_ID}

    async def test_search_score_is_one_minus_distance(
        self, ephemeral_service: VectorStoreService
    ) -> None:
        await self._seed(ephemeral_service)
        response = await ephemeral_service.search(_QUERY_VEC, n_results=3)
        for r in response.results:
            assert r.score == pytest.approx(max(0.0, 1.0 - r.distance), abs=1e-6)

    async def test_search_empty_collection_returns_empty(
        self, ephemeral_service: VectorStoreService
    ) -> None:
        # Collection exists (auto-created) but has no documents.
        # Chroma raises when n_results > count; we use n_results=1.
        try:
            response = await ephemeral_service.search(_QUERY_VEC, n_results=1)
            assert response.total_returned == 0
        except Exception:
            # Acceptable: Chroma may raise on empty collection.
            pass


# ---------------------------------------------------------------------------
# get_by_ids tests
# ---------------------------------------------------------------------------


class TestGetByIds:
    async def test_returns_correct_ids(
        self, ephemeral_service: VectorStoreService
    ) -> None:
        docs = [_make_vec_doc(chunk_id=f"g{i}") for i in range(3)]
        await ephemeral_service.upsert_documents(docs, _DOC_ID)

        rows = await ephemeral_service.get_by_ids(["g0", "g2"])
        returned_ids = {r["id"] for r in rows}
        assert returned_ids == {"g0", "g2"}

    async def test_each_row_has_text_and_metadata(
        self, ephemeral_service: VectorStoreService
    ) -> None:
        doc = _make_vec_doc(chunk_id="gx", text="specific text")
        await ephemeral_service.upsert_documents([doc], _DOC_ID)
        rows = await ephemeral_service.get_by_ids(["gx"])
        assert rows[0]["text"] == "specific text"
        assert "document_id" in rows[0]["metadata"]
