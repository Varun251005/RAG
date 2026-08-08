from fastapi import APIRouter

from app.api.v1 import audio, chat, documents, health, rag, tts, voice

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(documents.router, prefix="/documents", tags=["Documents"])
api_router.include_router(chat.router, prefix="/chat", tags=["Chat"])
api_router.include_router(rag.router, prefix="/rag", tags=["RAG"])
api_router.include_router(audio.router, prefix="/audio", tags=["Audio"])
api_router.include_router(tts.router, prefix="/tts", tags=["TTS"])
api_router.include_router(voice.router, prefix="/voice", tags=["Voice STT"])
