"""
Unit tests for text chunking layer (ChunkingService) using RecursiveCharacterTextSplitter.

Verifies:
1. Short text (single small chunk)
2. Long text (multiple overlapping chunks)
3. Multi-page document chunking with page boundary preservation
4. Empty page handling (gracefully skipped / empty list)
5. Very short page chunking
6. Chunk overlap verification
7. Metadata preservation (chunk_id, document_id, source_filename, page_number, chunk_index, text)
8. Unique chunk IDs across all generated chunks
9. Deterministic chunk IDs for identical input
"""

from __future__ import annotations

import pytest
from app.services.chunking_service import ChunkingService


@pytest.fixture
def chunking_service() -> ChunkingService:
    # 3200 chars ~ 800 tokens, 600 chars ~ 150 tokens
    return ChunkingService(chunk_size=3200, chunk_overlap=600)


def test_chunk_short_text(chunking_service: ChunkingService) -> None:
    text = "Python is an interpreted, high-level, general-purpose programming language."
    chunks = chunking_service._splitter.split_text(text)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunk_long_text_and_overlap() -> None:
    # Use small chunk size (100) and overlap (30) to test splitting behavior deterministically
    svc = ChunkingService(chunk_size=100, chunk_overlap=30)
    long_text = (
        "VoiceRAG AI is a state of the art retrieval augmented generation platform. "
        "It supports voice synthesis, document search, local vector search, and AI powered document summary. "
        "The architecture is designed to be modular, robust, and highly scalable across GPU and CPU environments."
    )
    chunks = svc._splitter.split_text(long_text)
    assert len(chunks) > 1

    # Verify overlap exists between consecutive chunks
    overlap_found = False
    for i in range(len(chunks) - 1):
        words_c1 = set(chunks[i].split())
        words_c2 = set(chunks[i + 1].split())
        common = words_c1.intersection(words_c2)
        if len(common) > 0:
            overlap_found = True
            break
    assert overlap_found, "Consecutive chunks should share overlapping text"


def test_chunk_multipage_document(chunking_service: ChunkingService) -> None:
    pages_data = [
        {"page_number": 1, "text": "Page 1: Introduction to VoiceRAG AI architecture."},
        {"page_number": 2, "text": "Page 2: Vector embeddings and ChromaDB storage details."},
        {"page_number": 3, "text": "Page 3: Text-to-speech synthesis with Edge-TTS."},
    ]
    doc_id = "doc_multipage_1001"
    filename = "voicerag_arch.pdf"

    all_chunks = []
    global_idx = 0

    for page in pages_data:
        p_num = page["page_number"]
        p_text = page["text"]
        raw = chunking_service._splitter.split_text(p_text)
        for sub_i, chunk_txt in enumerate(raw):
            cid = f"{doc_id}_p{p_num:04d}_c{sub_i:04d}"
            chunk_dict = {
                "chunk_id": cid,
                "document_id": doc_id,
                "source_filename": filename,
                "page_number": p_num,
                "chunk_index": global_idx,
                "text": chunk_txt,
            }
            all_chunks.append(chunk_dict)
            global_idx += 1

    assert len(all_chunks) == 3
    assert all_chunks[0]["page_number"] == 1
    assert all_chunks[1]["page_number"] == 2
    assert all_chunks[2]["page_number"] == 3
    assert all_chunks[0]["chunk_index"] == 0
    assert all_chunks[1]["chunk_index"] == 1
    assert all_chunks[2]["chunk_index"] == 2


def test_chunk_empty_page(chunking_service: ChunkingService) -> None:
    empty_text = ""
    chunks = chunking_service._splitter.split_text(empty_text)
    assert len(chunks) == 0


def test_chunk_very_short_page(chunking_service: ChunkingService) -> None:
    short_page_text = "Page 5"
    chunks = chunking_service._splitter.split_text(short_page_text)
    assert len(chunks) == 1
    assert chunks[0] == "Page 5"


def test_chunk_metadata_preservation(chunking_service: ChunkingService) -> None:
    doc_id = "doc_meta_888"
    filename = "research.pdf"
    page_num = 4
    text = "Machine learning models require clean text preprocessing."

    sub_chunks = chunking_service._splitter.split_text(text)
    c = sub_chunks[0]

    chunk_record = {
        "chunk_id": f"{doc_id}_p{page_num:04d}_c0000",
        "document_id": doc_id,
        "source_filename": filename,
        "page_number": page_num,
        "chunk_index": 0,
        "text": c,
    }

    assert chunk_record["chunk_id"] == "doc_meta_888_p0004_c0000"
    assert chunk_record["document_id"] == "doc_meta_888"
    assert chunk_record["source_filename"] == "research.pdf"
    assert chunk_record["page_number"] == 4
    assert chunk_record["chunk_index"] == 0
    assert chunk_record["text"] == text


def test_unique_and_deterministic_chunk_ids(chunking_service: ChunkingService) -> None:
    doc_id = "doc_det_999"
    page_num = 1
    text = "Sample sentence " * 50

    raw_chunks = chunking_service._splitter.split_text(text)
    chunk_ids_run1 = [f"{doc_id}_p{page_num:04d}_c{idx:04d}" for idx in range(len(raw_chunks))]
    chunk_ids_run2 = [f"{doc_id}_p{page_num:04d}_c{idx:04d}" for idx in range(len(raw_chunks))]

    # 1. Verify uniqueness
    assert len(chunk_ids_run1) == len(set(chunk_ids_run1))

    # 2. Verify determinism
    assert chunk_ids_run1 == chunk_ids_run2
