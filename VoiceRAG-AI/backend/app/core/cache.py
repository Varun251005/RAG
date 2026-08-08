"""
Async disk-backed embedding cache with an in-memory LRU front layer.

Architecture
------------
Two-tier:
  1. **L1 — in-memory dict** (bounded by ``max_memory_entries``).
     Ultra-fast; survives only for the process lifetime.
  2. **L2 — disk JSON files** (one file per entry, keyed by text_hash).
     Survives restarts; written atomically via a temp file → rename.

Cache key
---------
``SHA-256(chunk_text)`` — content-addressed so the same text always hits
the same entry regardless of chunk_id or document.  This naturally
deduplicates repeated passages across documents.

Thread / async safety
---------------------
All public methods are ``async``.  Disk I/O is run in the default thread-pool
executor (``asyncio.to_thread``) so the event loop is never blocked.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from app.models.embedding import CachedEmbedding, EmbeddingVector


class EmbeddingCache:
    """
    Two-tier (memory + disk) cache for embedding vectors.

    Parameters
    ----------
    cache_dir :
        Directory on disk for L2 cache files.  Created on first use.
    max_memory_entries :
        Maximum number of entries held in the L1 in-memory LRU dict.
        Oldest entries are evicted when the limit is reached.
    """

    def __init__(self, cache_dir: Path, max_memory_entries: int = 1024) -> None:
        self._cache_dir = cache_dir
        self._max_memory = max_memory_entries
        # OrderedDict used as a simple LRU: move-to-end on access.
        self._memory: OrderedDict[str, CachedEmbedding] = OrderedDict()
        self._lock = asyncio.Lock()

    # ── Public interface ───────────────────────────────────────────────────────

    @staticmethod
    def text_hash(text: str) -> str:
        """Return the SHA-256 hex digest of *text* — the cache key."""
        return hashlib.sha256(text.encode()).hexdigest()

    async def get(self, text: str) -> CachedEmbedding | None:
        """
        Look up *text* in the cache.

        Checks L1 first; falls back to L2 disk on miss.  Promotes a disk hit
        into L1 for subsequent fast access.

        Returns ``None`` on a total cache miss.
        """
        key = self.text_hash(text)

        async with self._lock:
            # L1 hit
            if key in self._memory:
                self._memory.move_to_end(key)
                logger.debug(f"Cache L1 hit | key={key[:8]}…")
                return self._memory[key]

        # L2 lookup (outside lock — disk I/O is slow)
        entry = await asyncio.to_thread(self._disk_get, key)
        if entry is not None:
            logger.debug(f"Cache L2 hit | key={key[:8]}…")
            async with self._lock:
                self._promote(key, entry)
        return entry

    async def put(self, text: str, chunk_id: str, vector: EmbeddingVector, model: str) -> None:
        """
        Store an embedding in both L1 and L2.

        Disk write is atomic: written to a temp file then renamed so a
        mid-write crash never corrupts an existing entry.
        """
        key = self.text_hash(text)
        entry = CachedEmbedding(
            chunk_id=chunk_id,
            text_hash=key,
            vector=vector,
            model=model,
            created_at=datetime.now(timezone.utc),
        )

        async with self._lock:
            self._promote(key, entry)

        await asyncio.to_thread(self._disk_put, key, entry)
        logger.debug(f"Cache write | key={key[:8]}… | chunk={chunk_id}")

    async def invalidate(self, text: str) -> None:
        """Remove an entry from both L1 and L2 (best-effort)."""
        key = self.text_hash(text)
        async with self._lock:
            self._memory.pop(key, None)
        await asyncio.to_thread(self._disk_delete, key)

    async def clear(self) -> None:
        """Wipe all cached embeddings from memory and disk."""
        async with self._lock:
            self._memory.clear()
        await asyncio.to_thread(self._disk_clear)
        logger.info("Embedding cache cleared")

    # ── Private — synchronous disk helpers (run via to_thread) ────────────────

    def _cache_path(self, key: str) -> Path:
        return self._cache_dir / f"{key}.json"

    def _disk_get(self, key: str) -> CachedEmbedding | None:
        path = self._cache_path(key)
        if not path.exists():
            return None
        try:
            return CachedEmbedding.model_validate_json(path.read_text())
        except Exception as exc:
            logger.warning(f"Corrupt cache entry | key={key[:8]}… | {exc}")
            return None

    def _disk_put(self, key: str, entry: CachedEmbedding) -> None:
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        tmp = self._cache_dir / f"_{uuid.uuid4().hex}.tmp"
        try:
            tmp.write_text(entry.model_dump_json())
            tmp.rename(self._cache_path(key))
        except OSError as exc:
            logger.error(f"Cache disk write failed | key={key[:8]}… | {exc}")
            tmp.unlink(missing_ok=True)

    def _disk_delete(self, key: str) -> None:
        self._cache_path(key).unlink(missing_ok=True)

    def _disk_clear(self) -> None:
        if not self._cache_dir.exists():
            return
        for f in self._cache_dir.glob("*.json"):
            f.unlink(missing_ok=True)

    # ── Private — LRU eviction ─────────────────────────────────────────────────

    def _promote(self, key: str, entry: CachedEmbedding) -> None:
        """Insert / move *entry* to the front of the LRU dict; evict if full."""
        self._memory[key] = entry
        self._memory.move_to_end(key)
        while len(self._memory) > self._max_memory:
            evicted_key, _ = self._memory.popitem(last=False)
            logger.debug(f"Cache L1 eviction | key={evicted_key[:8]}…")

    # ── Stats ──────────────────────────────────────────────────────────────────

    @property
    def memory_size(self) -> int:
        """Current number of entries in the L1 in-memory cache."""
        return len(self._memory)
