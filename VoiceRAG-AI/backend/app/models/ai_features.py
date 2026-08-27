+"""Pydantic models for Document AI Features (Summary, Flashcards, Quiz, Notes, Key Topics, FAQ)."""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, ConfigDict, Field


class AIFeatureType(str, Enum):
    """Supported document AI feature types."""

    SUMMARY = "summary"
    FLASHCARDS = "flashcards"
    QUIZ = "quiz"
    NOTES = "notes"
    KEY_TOPICS = "key_topics"
    FAQ = "faq"


class AIFeatureRequest(BaseModel):
    """Request payload for generating an AI document feature."""

    document_id: str | None = Field(default=None, description="Target document ID (or null for all docs).")
    feature: AIFeatureType = Field(description="AI feature type to generate.")
    collection: str | None = Field(default=None, description="Optional Chroma collection name.")

    model_config = ConfigDict(frozen=True)


class Flashcard(BaseModel):
    """A single study flashcard."""

    front: str = Field(description="Question or concept prompt on the front of the flashcard.")
    back: str = Field(description="Answer or detailed explanation on the back of the flashcard.")


class FlashcardsResponse(BaseModel):
    """List of generated flashcards."""

    flashcards: list[Flashcard]


class QuizQuestion(BaseModel):
    """A multiple-choice quiz question."""

    question: str
    options: list[str] = Field(description="List of 4 choices (A, B, C, D).")
    answer: str = Field(description="Correct choice text (matches one of options).")
    explanation: str = Field(description="Explanation of why this answer is correct.")


class QuizResponse(BaseModel):
    """Generated document quiz."""

    questions: list[QuizQuestion]
