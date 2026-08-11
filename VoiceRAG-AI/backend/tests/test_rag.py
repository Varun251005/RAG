"""
Unit and integration tests for the RAG pipeline (Phase 8).

All tests are fully mocked — no Gemini API key, no ChromaDB server,
no EmbeddingService required.

Test classes
------------
TestRAGServiceValidation   — question validation edge cases.
TestRAGServiceBatch        — batch query (query()) happy path + failures.
TestRAGServiceStreaming     — stream_query() SSE events.
TestRAGBuildHelpers         — _build_context, _build_sources, _sse.
TestRAGNoResults           — graceful handling when ChromaDB returns nothing.
TestRAGScoreThreshold      — chunk filtering by score threshold.
TestRAGAPI                 — HTTP-level tests via FastAPI test client.
TestIngestEndpoint         — /rag/ingest/{doc_id} endpoint.
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.api.deps as deps
from app.core.exceptions import ServiceError, UnprocessableError
from app.models.rag import RAGQuery, RAGResponse, RAGSource
from app.models.vector_store import SearchResponse, SearchResult
from app.services.rag_service import RAGService, _sse


# ---------------------------------------------------------------------------
# Constants & helpers
# ---------------------------------------------------------------------------

_DOC_ID = "doc-abc-123"
_QUESTION = "What is the refund policy?"
_ANSWER = "Refunds are processed within 30 days."
_FAKE_VECTOR = [0.1, 0.2, 0.3]
_MODEL = "gemini-2.0-flash"


def _make_result(
    chunk_id: str = "c0",
    text: str = "Refunds take 30 days.",
    page: int = 1,
    score: float = 0.9,
    doc_id: str = _DOC_ID,
) -> SearchResult:
    return SearchResult(
        id=chunk_id,
        text=text,
        metadata={
            "document_id": doc_id,
            "page_number": page,
            "original_filename": "policy.pdf",
        },
        distance=1.0 - score,
        score=score,
    )


def _make_search_response(results: list[SearchResult] | None = None) -> SearchResponse:
    results = results if results is not None else [_make_result()]
    return SearchResponse(
        query=_QUESTION,
        collection="voicerag",
        results=results,
        total_returned=len(results),
    )


def _make_rag_service(
    embed_return: list[float] | None = None,
    search_return: SearchResponse | None = None,
    chain_answer: str = _ANSWER,
    score_threshold: float = 0.0,
) -> RAGService:
    """Build a RAGService with all external calls mocked."""
    mock_emb_svc = MagicMock()
    mock_emb_svc.embed_text = AsyncMock(return_value=embed_return or _FAKE_VECTOR)

    mock_vs_svc = MagicMock()
    mock_vs_svc.search = AsyncMock(
        return_value=search_return if search_return is not None else _make_search_response()
    )
    mock_vs_svc.search_by_document = AsyncMock(
        return_value=search_return if search_return is not None else _make_search_response()
    )

    svc = RAGService(
        embedding_service=mock_emb_svc,
        vector_store_service=mock_vs_svc,
        api_key="fake-key",
        model=_MODEL,
        top_k=5,
        max_output_tokens=512,
        temperature=0.0,
        score_threshold=score_threshold,
    )

    # Patch the LangChain chain so no real Gemini call is made.
    mock_chain = MagicMock()
    mock_chain.ainvoke = AsyncMock(return_value=chain_answer)

    async def _fake_astream(*_a, **_kw) -> AsyncGenerator[str, None]:
        for token in chain_answer.split():
            yield token + " "

    mock_chain.astream = _fake_astream
    svc._chain = mock_chain

    return svc


# ---------------------------------------------------------------------------
# Test: question validation
# ---------------------------------------------------------------------------


class TestRAGServiceValidation:
    async def test_blank_question_raises(self) -> None:
        svc = _make_rag_service()
        with pytest.raises(UnprocessableError, match="blank"):
            await svc.query("   ")

    async def test_whitespace_only_question_raises(self) -> None:
        svc = _make_rag_service()
        with pytest.raises(UnprocessableError):
            await svc.query("\t\n")

    async def test_too_long_question_raises(self) -> None:
        svc = _make_rag_service()
        with pytest.raises(UnprocessableError, match="long"):
            await svc.query("x" * 2001)

    async def test_max_length_question_accepted(self) -> None:
        svc = _make_rag_service()
        response = await svc.query("x" * 2000)
        assert isinstance(response, RAGResponse)

    async def test_valid_question_accepted(self) -> None:
        svc = _make_rag_service()
        response = await svc.query(_QUESTION)
        assert response.question == _QUESTION


# ---------------------------------------------------------------------------
# Test: batch query
# ---------------------------------------------------------------------------


class TestRAGServiceBatch:
    async def test_returns_rag_response(self) -> None:
        svc = _make_rag_service()
        resp = await svc.query(_QUESTION)
        assert isinstance(resp, RAGResponse)

    async def test_answer_is_stripped(self) -> None:
        svc = _make_rag_service(chain_answer=f"  {_ANSWER}  ")
        resp = await svc.query(_QUESTION)
        assert resp.answer == _ANSWER

    async def test_question_echoed(self) -> None:
        svc = _make_rag_service()
        resp = await svc.query(_QUESTION)
        assert resp.question == _QUESTION

    async def test_model_name_present(self) -> None:
        svc = _make_rag_service()
        resp = await svc.query(_QUESTION)
        assert resp.model == _MODEL

    async def test_sources_populated(self) -> None:
        results = [_make_result(chunk_id=f"c{i}", page=i + 1) for i in range(3)]
        svc = _make_rag_service(search_return=_make_search_response(results))
        resp = await svc.query(_QUESTION)
        assert resp.total_chunks_used == 3
        assert len(resp.sources) == 3

    async def test_source_fields_correct(self) -> None:
        result = _make_result(chunk_id="cx", text="Policy text.", page=7, score=0.88)
        svc = _make_rag_service(search_return=_make_search_response([result]))
        resp = await svc.query(_QUESTION)
        src = resp.sources[0]
        assert src.chunk_id == "cx"
        assert src.page_number == 7
        assert src.score == pytest.approx(0.88)
        assert src.original_filename == "policy.pdf"
        assert src.document_id == _DOC_ID

    async def test_embed_called_once(self) -> None:
        svc = _make_rag_service()
        await svc.query(_QUESTION)
        svc._embedding_svc.embed_text.assert_called_once_with(_QUESTION)  # type: ignore[attr-defined]

    async def test_search_called_with_embedded_vector(self) -> None:
        svc = _make_rag_service(embed_return=[0.5, 0.6])
        await svc.query(_QUESTION)
        svc._vector_store_svc.search.assert_called_once()  # type: ignore[attr-defined]
        call_kwargs = svc._vector_store_svc.search.call_args.kwargs  # type: ignore[attr-defined]
        assert call_kwargs["query_vector"] == [0.5, 0.6]

    async def test_document_id_uses_search_by_document(self) -> None:
        svc = _make_rag_service()
        await svc.query(_QUESTION, document_id=_DOC_ID)
        svc._vector_store_svc.search_by_document.assert_called_once()  # type: ignore[attr-defined]
        svc._vector_store_svc.search.assert_not_called()  # type: ignore[attr-defined]

    async def test_top_k_override_passed_to_search(self) -> None:
        svc = _make_rag_service()
        await svc.query(_QUESTION, top_k=3)
        call_kwargs = svc._vector_store_svc.search.call_args.kwargs  # type: ignore[attr-defined]
        assert call_kwargs["n_results"] == 3

    async def test_embed_failure_raises_service_error(self) -> None:
        svc = _make_rag_service()
        svc._embedding_svc.embed_text = AsyncMock(  # type: ignore[attr-defined]
            side_effect=RuntimeError("embed died")
        )
        with pytest.raises(ServiceError, match="embed"):
            await svc.query(_QUESTION)

    async def test_search_failure_raises_service_error(self) -> None:
        svc = _make_rag_service()
        svc._vector_store_svc.search = AsyncMock(  # type: ignore[attr-defined]
            side_effect=RuntimeError("chroma died")
        )
        with pytest.raises(ServiceError, match="search"):
            await svc.query(_QUESTION)

    async def test_llm_failure_raises_service_error(self) -> None:
        svc = _make_rag_service()
        svc._chain.ainvoke = AsyncMock(side_effect=RuntimeError("llm died"))
        with pytest.raises(ServiceError, match="Generation"):
            await svc.query(_QUESTION)


# ---------------------------------------------------------------------------
# Test: streaming
# ---------------------------------------------------------------------------


class TestRAGServiceStreaming:
    async def _collect(self, gen: AsyncGenerator[str, None]) -> list[dict]:
        """Collect all SSE events from the stream into parsed dicts."""
        events: list[dict] = []
        async for line in gen:
            if line.startswith("event:"):
                # Parse: "event: <name>\ndata: <json>\n\n"
                parts = line.strip().split("\n")
                event_name = parts[0].split(": ", 1)[1]
                data = json.loads(parts[1].split(": ", 1)[1])
                events.append({"event": event_name, "data": data})
        return events

    async def test_stream_yields_token_events(self) -> None:
        svc = _make_rag_service(chain_answer="Hello world answer")
        events = await self._collect(svc.stream_query(_QUESTION))
        token_events = [e for e in events if e["event"] == "token"]
        assert len(token_events) >= 1
        assert all("text" in e["data"] for e in token_events)

    async def test_stream_yields_sources_event(self) -> None:
        svc = _make_rag_service()
        events = await self._collect(svc.stream_query(_QUESTION))
        src_events = [e for e in events if e["event"] == "sources"]
        assert len(src_events) == 1
        assert "sources" in src_events[0]["data"]
        assert "total_chunks_used" in src_events[0]["data"]

    async def test_stream_yields_done_event(self) -> None:
        svc = _make_rag_service()
        events = await self._collect(svc.stream_query(_QUESTION))
        done_events = [e for e in events if e["event"] == "done"]
        assert len(done_events) == 1

    async def test_stream_done_comes_after_sources(self) -> None:
        svc = _make_rag_service()
        events = await self._collect(svc.stream_query(_QUESTION))
        event_names = [e["event"] for e in events]
        # tokens before sources before done
        assert "sources" in event_names
        assert "done" in event_names
        assert event_names.index("sources") < event_names.index("done")

    async def test_stream_blank_question_yields_error(self) -> None:
        svc = _make_rag_service()
        events = await self._collect(svc.stream_query("   "))
        assert events[0]["event"] == "error"
        assert "detail" in events[0]["data"]

    async def test_stream_embed_failure_yields_error(self) -> None:
        svc = _make_rag_service()
        svc._embedding_svc.embed_text = AsyncMock(  # type: ignore[attr-defined]
            side_effect=RuntimeError("embed died")
        )
        events = await self._collect(svc.stream_query(_QUESTION))
        error_events = [e for e in events if e["event"] == "error"]
        assert len(error_events) == 1

    async def test_stream_concatenated_tokens_match_answer(self) -> None:
        answer = "The quick brown fox."
        svc = _make_rag_service(chain_answer=answer)
        events = await self._collect(svc.stream_query(_QUESTION))
        token_text = "".join(
            e["data"]["text"] for e in events if e["event"] == "token"
        )
        assert token_text.strip() == answer.strip()

    async def test_stream_sources_include_correct_count(self) -> None:
        results = [_make_result(chunk_id=f"c{i}") for i in range(4)]
        svc = _make_rag_service(search_return=_make_search_response(results))
        events = await self._collect(svc.stream_query(_QUESTION))
        src_event = next(e for e in events if e["event"] == "sources")
        assert src_event["data"]["total_chunks_used"] == 4


# ---------------------------------------------------------------------------
# Test: build helpers
# ---------------------------------------------------------------------------


class TestRAGBuildHelpers:
    def test_build_context_formats_chunks(self) -> None:
        svc = _make_rag_service()
        results = [
            _make_result(chunk_id="c0", text="First chunk.", page=1),
            _make_result(chunk_id="c1", text="Second chunk.", page=2),
        ]
        context = svc._build_context(results)
        assert "First chunk." in context
        assert "Second chunk." in context
        assert "page 1" in context
        assert "page 2" in context
        assert "[Chunk 1" in context
        assert "[Chunk 2" in context

    def test_build_context_empty_returns_no_context_message(self) -> None:
        svc = _make_rag_service()
        ctx = svc._build_context([])
        assert "No relevant context" in ctx

    def test_build_sources_snippet_truncated(self) -> None:
        svc = _make_rag_service()
        long_text = "X" * 500
        result = _make_result(text=long_text)
        sources = svc._build_sources([result])
        assert len(sources[0].snippet) == 250

    def test_build_sources_short_text_not_truncated(self) -> None:
        svc = _make_rag_service()
        result = _make_result(text="Short.")
        sources = svc._build_sources([result])
        assert sources[0].snippet == "Short."

    def test_sse_format(self) -> None:
        line = _sse("token", {"text": "hello"})
        assert line.startswith("event: token\n")
        assert "data: " in line
        assert line.endswith("\n\n")
        parsed = json.loads(line.split("data: ", 1)[1].strip())
        assert parsed["text"] == "hello"

    def test_sse_unicode_preserved(self) -> None:
        line = _sse("token", {"text": "héllo wörld"})
        parsed = json.loads(line.split("data: ", 1)[1].strip())
        assert parsed["text"] == "héllo wörld"


# ---------------------------------------------------------------------------
# Test: no results
# ---------------------------------------------------------------------------


class TestRAGNoResults:
    async def test_empty_search_uses_no_context_message(self) -> None:
        svc = _make_rag_service(search_return=_make_search_response([]))
        resp = await svc.query(_QUESTION)
        # Chain was still called — the LLM will see "No relevant context"
        svc._chain.ainvoke.assert_called_once()  # type: ignore[attr-defined]
        call_args = svc._chain.ainvoke.call_args[0][0]
        assert "No relevant context" in call_args["context"]

    async def test_empty_search_returns_zero_sources(self) -> None:
        svc = _make_rag_service(search_return=_make_search_response([]))
        resp = await svc.query(_QUESTION)
        assert resp.total_chunks_used == 0
        assert resp.sources == []


# ---------------------------------------------------------------------------
# Test: score threshold filtering
# ---------------------------------------------------------------------------


class TestRAGScoreThreshold:
    async def test_chunks_below_threshold_excluded(self) -> None:
        results = [
            _make_result(chunk_id="high", score=0.9),
            _make_result(chunk_id="low", score=0.2),
        ]
        svc = _make_rag_service(
            search_return=_make_search_response(results),
            score_threshold=0.5,
        )
        resp = await svc.query(_QUESTION)
        assert resp.total_chunks_used == 1
        assert resp.sources[0].chunk_id == "high"

    async def test_all_chunks_pass_zero_threshold(self) -> None:
        results = [_make_result(chunk_id=f"c{i}", score=0.1 * i) for i in range(5)]
        svc = _make_rag_service(
            search_return=_make_search_response(results),
            score_threshold=0.0,
        )
        resp = await svc.query(_QUESTION)
        assert resp.total_chunks_used == 5

    async def test_all_chunks_filtered_out(self) -> None:
        results = [_make_result(score=0.1), _make_result(score=0.2)]
        svc = _make_rag_service(
            search_return=_make_search_response(results),
            score_threshold=0.99,
        )
        resp = await svc.query(_QUESTION)
        assert resp.total_chunks_used == 0


# ---------------------------------------------------------------------------
# Test: API endpoints (HTTP layer)
# ---------------------------------------------------------------------------


class TestRAGAPI:
    """Tests for the FastAPI RAG endpoints.  RAGService is injected as a mock."""

    @pytest.fixture(autouse=True)
    def inject_mock_rag_service(self) -> None:
        """Replace the RAGService singleton with a pre-wired mock."""
        mock_svc = MagicMock()
        mock_svc.query = AsyncMock(
            return_value=RAGResponse(
                question=_QUESTION,
                answer=_ANSWER,
                sources=[
                    RAGSource(
                        chunk_id="c0",
                        snippet="Policy text.",
                        page_number=1,
                        original_filename="policy.pdf",
                        score=0.9,
                        document_id=_DOC_ID,
                    )
                ],
                total_chunks_used=1,
                model=_MODEL,
            )
        )

        async def _fake_stream(*_a, **_kw) -> AsyncGenerator[str, None]:
            yield _sse("token", {"text": "Hello"})
            yield _sse("token", {"text": " world"})
            yield _sse("sources", {"sources": [], "total_chunks_used": 0})
            yield _sse("done", {})

        mock_svc.stream_query = _fake_stream
        deps._rag_service = mock_svc

    async def test_batch_query_200(self, client) -> None:
        response = await client.post(
            "/api/v1/rag/query",
            json={"question": _QUESTION},
        )
        assert response.status_code == 200

    async def test_batch_query_response_shape(self, client) -> None:
        response = await client.post(
            "/api/v1/rag/query",
            json={"question": _QUESTION},
        )
        body = response.json()
        assert body["question"] == _QUESTION
        assert body["answer"] == _ANSWER
        assert isinstance(body["sources"], list)
        assert body["total_chunks_used"] == 1
        assert body["model"] == _MODEL

    async def test_batch_query_source_fields(self, client) -> None:
        response = await client.post(
            "/api/v1/rag/query",
            json={"question": _QUESTION},
        )
        src = response.json()["sources"][0]
        assert src["chunk_id"] == "c0"
        assert src["page_number"] == 1
        assert src["score"] == pytest.approx(0.9)

    async def test_stream_endpoint_200(self, client) -> None:
        response = await client.post(
            "/api/v1/rag/stream",
            json={"question": _QUESTION},
        )
        assert response.status_code == 200

    async def test_stream_content_type(self, client) -> None:
        response = await client.post(
            "/api/v1/rag/stream",
            json={"question": _QUESTION},
        )
        assert "text/event-stream" in response.headers["content-type"]

    async def test_stream_body_contains_events(self, client) -> None:
        response = await client.post(
            "/api/v1/rag/stream",
            json={"question": _QUESTION},
        )
        body = response.text
        assert "event: token" in body
        assert "event: sources" in body
        assert "event: done" in body

    async def test_batch_query_rejects_blank_question(self, client) -> None:
        """422 is raised by Pydantic min_length before even hitting the service."""
        response = await client.post(
            "/api/v1/rag/query",
            json={"question": ""},
        )
        assert response.status_code == 422

    async def test_batch_query_rejects_too_long_question(self, client) -> None:
        response = await client.post(
            "/api/v1/rag/query",
            json={"question": "q" * 2001},
        )
        assert response.status_code == 422

    async def test_batch_query_top_k_validation(self, client) -> None:
        response = await client.post(
            "/api/v1/rag/query",
            json={"question": _QUESTION, "top_k": 0},
        )
        assert response.status_code == 422

    async def test_batch_query_top_k_too_large(self, client) -> None:
        response = await client.post(
            "/api/v1/rag/query",
            json={"question": _QUESTION, "top_k": 21},
        )
        assert response.status_code == 422

    async def test_batch_query_document_id_optional(self, client) -> None:
        response = await client.post(
            "/api/v1/rag/query",
            json={"question": _QUESTION, "document_id": _DOC_ID},
        )
        assert response.status_code == 200
