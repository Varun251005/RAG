"""
ChromaDB vector-store service.

Features
--------
* **Collections** — named, persistent collections; auto-created on first use
  or returned if they already exist.
* **Store chunks** — upserts ``VectorDocument`` objects so repeated ingestion
  is idempotent (Chroma upsert semantics).
* **Store metadata** — every chunk carries a flat metadata dict (page number,
  document ID, filename, etc.) stored alongside the vector.
* **Delete** — removes all chunks belonging to a given document from the
  collection (by ``document_id`` metadata filter).
* **Update** — re-upserts vectors/text/metadata for existing chunk IDs;
  Chroma's upsert is naturally an update when the ID exists.
* **Persistence** — handled by the ChromaDB server (Docker volume) when using
  ``AsyncHttpClient``; zero extra code required on our side.
* **Search** — async cosine similarity search returning ranked
  ``SearchResult`` objects with ``distance`` and ``score``.
* **Reusable / injectable** — singleton provided via ``deps.get_vector_store``.

Architecture
------------
We use ``chromadb.AsyncHttpClient`` (the async, HTTP-based client) so the
service integrates cleanly into FastAPI's event loop without thread-pool
overhead.  The client is lazily initialised and shared for the process
lifetime.

Chroma metadata constraint
--------------------------
Chroma only accepts flat metadata values of type ``str | int | float | bool``.
Complex Python objects (lists, nested dicts, datetimes) are serialised to
JSON strings by ``_flatten_metadata`` before being stored.

Configuration (``app.core.config.Settings``)
--------------------------------------------
    CHROMA_HOST        — ChromaDB host (default: localhost)
    CHROMA_PORT        — ChromaDB port (default: 8001)
    CHROMA_COLLECTION  — default collection name (default: voicerag)
"""

from __future__ import annotations

import inspect
import json
from typing import Any, TypeVar

import chromadb
from chromadb import AsyncClientAPI
from loguru import logger

from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ServiceError
from app.models.chunk import DocumentChunk
from app.models.embedding import EmbeddingRecord
from app.models.vector_store import (
    CollectionInfo,
    DeleteResult,
    SearchResponse,
    SearchResult,
    UpsertResult,
    VectorDocument,
)

# Maximum chunks per single Chroma upsert call.  Chroma recommends ≤ 5 461
# items per call; we stay well below to avoid HTTP body limits.
_UPSERT_BATCH_SIZE = 500

T = TypeVar("T")


async def _maybe_await(val: T) -> Any:
    """Helper to handle both sync and async return values from ChromaDB client/collection methods."""
    if inspect.isawaitable(val):
        return await val
    return val


class VectorStoreService:
    """Async service for all ChromaDB operations."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        default_collection: str | None = None,
        persist_dir: str | None = None,
        mode: str | None = None,
    ) -> None:
        cfg = get_settings()

        self._host: str = host or cfg.chroma_host
        self._port: int = port or cfg.chroma_port
        self._default_collection: str = default_collection or cfg.chroma_collection
        self._persist_dir: str = persist_dir or getattr(cfg, "chroma_persist_dir", ".chroma")
        self._mode: str = (mode or getattr(cfg, "chroma_mode", "persistent")).lower()

        # Lazily initialised — avoids blocking the import path.
        self._client: AsyncClientAPI | None = None

        logger.debug(
            f"VectorStoreService configured | "
            f"mode={self._mode} | "
            f"host={self._host}:{self._port} | "
            f"collection={self._default_collection}"
        )

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    async def connect(self) -> None:
        """Explicitly initialise the ChromaDB HTTP client."""
        await self._get_client()
        logger.info(f"ChromaDB connected | {self._host}:{self._port}")

    async def close(self) -> None:
        """Release the HTTP client."""
        self._client = None
        logger.debug("ChromaDB client released")

    # ── Collection management ──────────────────────────────────────────────────

    async def get_or_create_collection(
        self,
        name: str | None = None,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        """Return the named collection, creating it if it does not exist."""
        cname = name or self._default_collection
        client = await self._get_client()
        collection = await _maybe_await(
            client.get_or_create_collection(
                name=cname,
                metadata=metadata or {"hnsw:space": "cosine"},
            )
        )
        logger.debug(f"Collection ready | name={cname}")
        return collection

    async def delete_collection(self, name: str | None = None) -> None:
        """Permanently delete a collection and all its data."""
        cname = name or self._default_collection
        client = await self._get_client()
        try:
            await _maybe_await(client.delete_collection(cname))
            logger.info(f"Collection deleted | name={cname}")
        except Exception as exc:
            if "does not exist" in str(exc).lower():
                raise NotFoundError("Collection", cname) from exc
            raise ServiceError(f"Failed to delete collection '{cname}': {exc}") from exc

    async def collection_info(self, name: str | None = None) -> CollectionInfo:
        """Return the name and document count for a collection."""
        cname = name or self._default_collection
        collection = await self.get_or_create_collection(cname)
        count = await _maybe_await(collection.count())
        return CollectionInfo(name=cname, count=count)

    async def list_collections(self) -> list[CollectionInfo]:
        """Return info for every collection in the ChromaDB server."""
        client = await self._get_client()
        try:
            collections = await _maybe_await(client.list_collections())
        except Exception as exc:
            raise ServiceError(f"Failed to list collections: {exc}") from exc

        infos: list[CollectionInfo] = []
        for col in collections:
            try:
                col_name = col.name if hasattr(col, "name") else str(col)
                async_col = await _maybe_await(client.get_collection(col_name))
                count = await _maybe_await(async_col.count())
                infos.append(CollectionInfo(name=col_name, count=count))
            except Exception:
                col_name = col.name if hasattr(col, "name") else str(col)
                infos.append(CollectionInfo(name=col_name, count=0))
        return infos

    # ── Store (upsert) ─────────────────────────────────────────────────────────

    async def upsert_documents(
        self,
        documents: list[VectorDocument],
        document_id: str,
        collection_name: str | None = None,
    ) -> UpsertResult:
        """Upsert a list of VectorDocument objects into the collection."""
        if not documents:
            logger.warning(f"upsert_documents called with empty list | doc={document_id}")
            return UpsertResult(
                collection=collection_name or self._default_collection,
                upserted=0,
                document_id=document_id,
            )

        cname = collection_name or self._default_collection
        collection = await self.get_or_create_collection(cname)

        total_upserted = 0
        for batch in _batched(documents, _UPSERT_BATCH_SIZE):
            ids = [d.id for d in batch]
            embeddings = [d.embedding for d in batch]
            texts = [d.text for d in batch]
            metadatas = [_flatten_metadata(d.metadata) for d in batch]

            try:
                await _maybe_await(
                    collection.upsert(
                        ids=ids,
                        embeddings=embeddings,  # type: ignore[arg-type]
                        documents=texts,
                        metadatas=metadatas,  # type: ignore[arg-type]
                    )
                )
                total_upserted += len(batch)
                logger.debug(
                    f"Upserted batch | collection={cname} | "
                    f"doc={document_id} | count={len(batch)}"
                )
            except Exception as exc:
                raise ServiceError(
                    f"ChromaDB upsert failed for document '{document_id}': {exc}"
                ) from exc

        logger.info(
            f"Upsert complete | collection={cname} | "
            f"doc={document_id} | total={total_upserted}"
        )
        return UpsertResult(
            collection=cname,
            upserted=total_upserted,
            document_id=document_id,
        )

    async def upsert_from_chunks_and_embeddings(
        self,
        chunks: list[DocumentChunk],
        embeddings: list[EmbeddingRecord],
        document_id: str,
        collection_name: str | None = None,
    ) -> UpsertResult:
        """Convenience method — zips DocumentChunk with EmbeddingRecord and calls upsert_documents."""
        if len(chunks) != len(embeddings):
            raise ValueError(
                f"chunks ({len(chunks)}) and embeddings ({len(embeddings)}) "
                "must have the same length"
            )

        emb_map = {e.chunk_id: e for e in embeddings}
        docs: list[VectorDocument] = []

        for chunk in chunks:
            emb = emb_map.get(chunk.chunk_id)
            if emb is None:
                raise ValueError(
                    f"No embedding found for chunk_id='{chunk.chunk_id}'"
                )
            docs.append(
                VectorDocument(
                    id=chunk.chunk_id,
                    embedding=emb.vector,
                    text=chunk.text,
                    metadata={
                        "document_id": chunk.metadata.document_id,
                        "original_filename": chunk.metadata.original_filename,
                        "page_number": chunk.metadata.page_number,
                        "total_pages": chunk.metadata.total_pages,
                        "chunk_index": chunk.chunk_index,
                        "embedding_model": emb.model,
                        **{
                            f"extra_{k}": str(v)
                            for k, v in chunk.metadata.extra.items()
                        },
                    },
                )
            )

        return await self.upsert_documents(docs, document_id, collection_name)

    # ── Delete ─────────────────────────────────────────────────────────────────

    async def delete_document(
        self,
        document_id: str,
        collection_name: str | None = None,
    ) -> DeleteResult:
        """Delete all chunks belonging to document_id from the collection."""
        cname = collection_name or self._default_collection
        collection = await self.get_or_create_collection(cname)

        try:
            existing = await _maybe_await(
                collection.get(
                    where={"document_id": document_id},
                    include=[],
                )
            )
            ids_to_delete: list[str] = existing["ids"]
        except Exception as exc:
            raise ServiceError(
                f"ChromaDB get failed while preparing delete "
                f"for document '{document_id}': {exc}"
            ) from exc

        if not ids_to_delete:
            raise NotFoundError("Document chunks", document_id)

        try:
            await _maybe_await(collection.delete(ids=ids_to_delete))
            logger.info(
                f"Deleted chunks | collection={cname} | "
                f"doc={document_id} | count={len(ids_to_delete)}"
            )
        except Exception as exc:
            raise ServiceError(
                f"ChromaDB delete failed for document '{document_id}': {exc}"
            ) from exc

        return DeleteResult(
            collection=cname,
            document_id=document_id,
            deleted=len(ids_to_delete),
        )

    async def delete_by_ids(
        self,
        ids: list[str],
        collection_name: str | None = None,
    ) -> int:
        """Delete specific chunk IDs."""
        if not ids:
            return 0
        cname = collection_name or self._default_collection
        collection = await self.get_or_create_collection(cname)
        try:
            await _maybe_await(collection.delete(ids=ids))
            logger.debug(f"Deleted by IDs | collection={cname} | count={len(ids)}")
        except Exception as exc:
            raise ServiceError(f"ChromaDB delete_by_ids failed: {exc}") from exc
        return len(ids)

    # ── Search ─────────────────────────────────────────────────────────────────

    async def search(
        self,
        query_vector: list[float],
        query_text: str = "",
        n_results: int = 5,
        collection_name: str | None = None,
        where: dict[str, Any] | None = None,
    ) -> SearchResponse:
        """Run a vector similarity search against the collection."""
        cname = collection_name or self._default_collection
        collection = await self.get_or_create_collection(cname)

        query_kwargs: dict[str, Any] = {
            "query_embeddings": [query_vector],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            query_kwargs["where"] = where

        try:
            raw = await _maybe_await(collection.query(**query_kwargs))
        except Exception as exc:
            raise ServiceError(f"ChromaDB query failed: {exc}") from exc

        ids: list[str] = raw["ids"][0] if raw.get("ids") else []
        docs: list[str] = raw["documents"][0] if raw.get("documents") else []
        metas: list[dict[str, Any]] = raw["metadatas"][0] if raw.get("metadatas") else []
        dists: list[float] = raw["distances"][0] if raw.get("distances") else []

        results: list[SearchResult] = [
            SearchResult(
                id=sid,
                text=doc,
                metadata=meta,
                distance=dist,
                score=max(0.0, 1.0 - dist),
            )
            for sid, doc, meta, dist in zip(ids, docs, metas, dists, strict=False)
        ]

        logger.debug(
            f"Search complete | collection={cname} | "
            f"n_results={len(results)} | query_len={len(query_text)}"
        )

        return SearchResponse(
            query=query_text,
            collection=cname,
            results=results,
            total_returned=len(results),
        )

    async def search_by_document(
        self,
        query_vector: list[float],
        document_id: str,
        query_text: str = "",
        n_results: int = 5,
        collection_name: str | None = None,
    ) -> SearchResponse:
        """Search restricted to chunks from a single document."""
        return await self.search(
            query_vector=query_vector,
            query_text=query_text,
            n_results=n_results,
            collection_name=collection_name,
            where={"document_id": document_id},
        )

    # ── Raw get ────────────────────────────────────────────────────────────────

    async def get_by_ids(
        self,
        ids: list[str],
        collection_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve chunks by their IDs."""
        cname = collection_name or self._default_collection
        collection = await self.get_or_create_collection(cname)
        try:
            raw = await _maybe_await(
                collection.get(
                    ids=ids,
                    include=["documents", "metadatas"],
                )
            )
        except Exception as exc:
            raise ServiceError(f"ChromaDB get_by_ids failed: {exc}") from exc

        return [
            {"id": sid, "text": doc, "metadata": meta}
            for sid, doc, meta in zip(
                raw.get("ids", []),
                raw.get("documents", []) or [],
                raw.get("metadatas", []) or [],
                strict=False,
            )
        ]

    # ── Private ────────────────────────────────────────────────────────────────

    async def _get_client(self) -> AsyncClientAPI:
        """Return the lazily-initialised ChromaDB client.

        In 'persistent' mode (default for CPU-only dev environments) the
        embedded PersistentClient is used — no Docker/server required.
        In 'http' mode an AsyncHttpClient is created against chroma_host:chroma_port.
        """
        if self._client is None:
            try:
                if self._mode == "persistent":
                    import os
                    os.makedirs(self._persist_dir, exist_ok=True)
                    self._client = chromadb.PersistentClient(path=self._persist_dir)  # type: ignore[assignment]
                    logger.info(f"ChromaDB PersistentClient ready | path={self._persist_dir}")
                else:
                    self._client = await chromadb.AsyncHttpClient(
                        host=self._host,
                        port=self._port,
                    )
                    logger.debug(
                        f"ChromaDB AsyncHttpClient created | "
                        f"{self._host}:{self._port}"
                    )
            except Exception as exc:
                raise ServiceError(
                    f"Cannot connect to ChromaDB at "
                    f"{self._host}:{self._port} — {exc}"
                ) from exc
        return self._client


def _batched(items: list[VectorDocument], size: int) -> list[list[VectorDocument]]:
    """Partition items into consecutive batches of at most size."""
    return [items[i : i + size] for i in range(0, len(items), size)]


def _flatten_metadata(metadata: dict[str, Any]) -> dict[str, str | int | float | bool]:
    """Convert a metadata dict to only contain Chroma-compatible scalar types."""
    flat: dict[str, str | int | float | bool] = {}
    for key, value in metadata.items():
        if isinstance(value, bool | int | float | str):
            flat[key] = value
        else:
            flat[key] = json.dumps(value, default=str)
    return flat
