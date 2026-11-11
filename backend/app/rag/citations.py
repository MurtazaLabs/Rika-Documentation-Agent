"""Citation markers and validation against retrieved source metadata.

The model is asked to write inline markers such as ``[S1]``. Only markers that
refer to a source included in the prompt become citations; unknown markers are
removed from the answer instead of being presented as verified references.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Sequence

from app.rag.types import PromptSource

_MARKER_GROUP = re.compile(
    r"\[((?:S\d+)(?:\s*[,;]\s*S\d+)*)\]",
    re.IGNORECASE,
)
_MARKER = re.compile(r"S(\d+)", re.IGNORECASE)
SNIPPET_CHARS = 280


@dataclass(frozen=True, slots=True)
class Citation:
    """One verified citation, built from stored chunk metadata."""

    marker: str
    chunk_id: str
    document_id: str
    file_path: str
    filename: str
    file_type: str
    content_type: str
    language: str | None
    symbol_name: str | None
    symbol_type: str | None
    start_line: int | None
    end_line: int | None
    page_number: int | None
    snippet: str
    rank: int
    retrieval_score: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "marker": self.marker,
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "file_path": self.file_path,
            "filename": self.filename,
            "file_type": self.file_type,
            "content_type": self.content_type,
            "language": self.language,
            "symbol_name": self.symbol_name,
            "symbol_type": self.symbol_type,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "page_number": self.page_number,
            "snippet": self.snippet,
            "rank": self.rank,
            "retrieval_score": self.retrieval_score,
        }


@dataclass(slots=True)
class CitationValidation:
    """The cleaned answer plus the citations that survived validation."""

    text: str
    citations: list[dict[str, Any]]
    invalid_markers: list[str]

    @property
    def has_citations(self) -> bool:
        return bool(self.citations)


def validate_citations(
    text: str, sources: Sequence[PromptSource]
) -> CitationValidation:
    """Resolve ``[S#]`` markers against the included sources.

    Valid markers are kept, duplicate markers collapse to their first
    appearance, and markers that name a source the model was never given are
    deleted. The returned citations are ordered by first mention.
    """
    source_map = {source.marker.upper(): source for source in sources}
    citations: list[Citation] = []
    cited: set[str] = set()
    invalid: list[str] = []

    def _replace(group: re.Match[str]) -> str:
        markers: list[str] = []
        for raw in _MARKER.findall(group.group(1)):
            marker = f"S{int(raw)}"
            key = marker.upper()
            if key not in source_map:
                invalid.append(marker)
                continue
            if key not in cited:
                cited.add(key)
                citations.append(_citation_for(source_map[key]))
            if marker not in markers:
                markers.append(marker)
        if not markers:
            return ""
        return "[" + ", ".join(markers) + "]"

    cleaned = _MARKER_GROUP.sub(_replace, text)
    # Removing a marker can leave a space before punctuation.
    cleaned = re.sub(r"[ \t]+([.,;:!?])", r"\1", cleaned).strip()

    return CitationValidation(
        text=cleaned,
        citations=[citation.as_dict() for citation in citations],
        invalid_markers=sorted(set(invalid), key=_marker_number),
    )


def _citation_for(source: PromptSource) -> Citation:
    hit = source.hit
    chunk = hit.chunk
    metadata = chunk.metadata_ or {}
    return Citation(
        marker=source.marker,
        chunk_id=str(chunk.id),
        document_id=str(chunk.document_id),
        file_path=hit.file_path,
        filename=hit.filename,
        file_type=hit.file_type,
        content_type=chunk.content_type,
        language=_optional_text(chunk.language or metadata.get("language")),
        symbol_name=chunk.symbol_name,
        symbol_type=_optional_text(metadata.get("symbol_type")),
        start_line=chunk.start_line,
        end_line=chunk.end_line,
        page_number=chunk.page_number,
        snippet=_snippet(chunk.content),
        rank=hit.rank,
        retrieval_score=hit.score,
    )


def _optional_text(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _snippet(content: str) -> str:
    text = " ".join(content.split())
    if len(text) <= SNIPPET_CHARS:
        return text
    return text[: SNIPPET_CHARS - 3].rstrip() + "..."


def _marker_number(marker: str) -> int:
    match = _MARKER.fullmatch(marker)
    return int(match.group(1)) if match else 0
