"""
Chat API Router — handles RAG question-answering endpoint over indexed document chunks.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from loguru import logger

from app.api.deps import get_ollama_llm_service, get_retrieval_service
from app.models.chat_api import ChatRequest, ChatResponse, ChatSourceCitation
from app.services.llm_service import OllamaLLMService
from app.services.retrieval_service import RAGRetrievalService

router = APIRouter()


@router.post(
    "",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask a question about indexed documents (RAG Chat)",
    description=(
        "Retrieves top relevant chunks from ChromaDB using local 384-dim CPU embeddings, "
        "builds a grounded context prompt, and generates an answer using local Qwen via Ollama."
    ),
)
async def chat_query(
    request: ChatRequest,
    retrieval_service: RAGRetrievalService = Depends(get_retrieval_service),
    llm_service: OllamaLLMService = Depends(get_ollama_llm_service),
) -> ChatResponse:
    question = (request.question or "").strip()
    logger.info(f"Chat request received | question='{question[:40]}...' | document_id={request.document_id}")

    # 1. Retrieve relevant chunks from ChromaDB
    retrieved_chunks = await retrieval_service.retrieve_relevant_chunks(
        question=question,
        document_id=request.document_id,
    )

    # 2. Generate grounded answer via Ollama Qwen LLM
    rag_response = await llm_service.generate_rag_answer(
        question=question,
        retrieved_chunks=retrieved_chunks,
    )

    # 3. Format sources
    sources = [
        ChatSourceCitation(
            document_id=src.document_id,
            filename=src.filename,
            page_number=src.page_number,
            chunk_id=src.chunk_id,
        )
        for src in rag_response.sources
    ]

    return ChatResponse(
        answer=rag_response.answer,
        sources=sources,
    )
