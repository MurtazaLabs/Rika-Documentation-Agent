"""Result types shared by the retrieval stages."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from app.database.models import DocumentChunk


@dataclass(frozen=True, slots=True)
class SearchFilters:
    """Metadata filters applied to every retrieval query.

    ``project_id`` is not a field: it is supplied separately by the API path
    and added to every SQL predicate, so a caller cannot widen the scope.
    """

    file_path: str | None = None
    file_type: str | None = None
    language: str | None = None
    symbol_type: str | None = None
    directory: str | None = None
    document_type: str | None = None


@dataclass(slots=True)
class ChunkCandidate:
    """One chunk returned by a single retrieval signal.

    ``file_path``, ``filename`` and ``file_type`` come from the owning
    ``documents`` row, not from the chunk's JSON metadata, so the citation is
    always the path the user uploaded.
    """

    chunk: DocumentChunk
    file_path: str
    filename: str
    file_type: str
    vector_score: float | None = None
    keyword_score: float | None = None


@dataclass(slots=True)
class RetrievedChunk:
    """A fused, ranked result ready to be serialised by the API."""

    chunk: DocumentChunk
    file_path: str
    filename: str
    file_type: str
    rank: int
    score: float
    vector_score: float | None = None
    keyword_score: float | None = None
    matched_by: tuple[str, ...] = field(default_factory=tuple)

    @property
    def chunk_id(self) -> uuid.UUID:
        return self.chunk.id

    @property
    def document_id(self) -> uuid.UUID:
        return self.chunk.document_id
