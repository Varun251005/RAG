from fastapi import APIRouter

from app.api.v1 import audio, documents, health, rag, tts

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(documents.router, prefix="/documents", tags=["Documents"])
api_router.include_router(rag.router, prefix="/rag", tags=["RAG"])
api_router.include_router(audio.router, prefix="/audio", tags=["Audio"])
api_router.include_router(tts.router, prefix="/tts", tags=["TTS"])


