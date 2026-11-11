"""Retrieval-augmented prompt assembly and citation validation."""

from __future__ import annotations

from app.rag.citations import Citation, CitationValidation, validate_citations
from app.rag.prompts import (
    RIKA_SYSTEM_PROMPT,
    build_chat_messages,
    build_context,
    build_retrieval_query,
)
from app.rag.types import HistoryTurn, PromptSource

__all__ = [
    "Citation",
    "CitationValidation",
    "HistoryTurn",
    "PromptSource",
    "RIKA_SYSTEM_PROMPT",
    "build_chat_messages",
    "build_context",
    "build_retrieval_query",
    "validate_citations",
]
