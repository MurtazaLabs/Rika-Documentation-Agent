"""Line-aware chunking.

Chunks are cut on line boundaries with a trailing overlap, so a citation can
always name a line range that exists in the source file. Nothing here touches
the database or the embedding model.

Document parsers may split a file into structural segments (a PDF page, a
Word section, a slide, a sheet). :func:`chunk_segments` chunks each segment
independently and keeps its metadata on every resulting chunk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ChunkDraft:
    index: int
    text: str
    start_line: int
    end_line: int
    symbol_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def chunk_text(
    text: str, *, max_chars: int = 1200, overlap_chars: int = 200
) -> list[ChunkDraft]:
    """Split ``text`` into overlapping chunks of at most ``max_chars``."""
    if max_chars < 1:
        raise ValueError("max_chars must be positive")
    if overlap_chars < 0:
        raise ValueError("overlap_chars cannot be negative")
    overlap_chars = min(overlap_chars, max_chars // 2)

    pieces = list(_line_pieces(text, max_chars))
    if not pieces:
        return []

    drafts: list[ChunkDraft] = []
    buffer: list[tuple[int, str]] = []
    length = 0

    for line_number, piece in pieces:
        addition = len(piece) + (1 if buffer else 0)
        if buffer and length + addition > max_chars:
            drafts.append(_draft(len(drafts), buffer))
            buffer = _overlap_tail(buffer, overlap_chars)
            length = sum(len(text) + 1 for _, text in buffer)
            if buffer:
                length -= 1

        buffer.append((line_number, piece))
        length += len(piece) + (1 if len(buffer) > 1 else 0)

    if buffer:
        drafts.append(_draft(len(drafts), buffer))

    return [draft for draft in drafts if draft.text.strip()]


def chunk_segments(
    segments: list[Any],
    *,
    max_chars: int = 1200,
    overlap_chars: int = 200,
) -> list[ChunkDraft]:
    """Chunk each parsed segment, offsetting lines into the flat text.

    ``segments`` are :class:`app.ingestion.parsers.ParsedSegment` values. Each
    one's metadata (page, slide, sheet, section) is copied onto every chunk.
    """
    drafts: list[ChunkDraft] = []
    for segment in segments:
        offset = max(int(getattr(segment, "start_line", 1) or 1) - 1, 0)
        metadata = dict(getattr(segment, "metadata", {}) or {})
        for local in chunk_text(
            segment.text, max_chars=max_chars, overlap_chars=overlap_chars
        ):
            drafts.append(
                ChunkDraft(
                    index=len(drafts),
                    text=local.text,
                    start_line=local.start_line + offset,
                    end_line=local.end_line + offset,
                    metadata=dict(metadata),
                )
            )
    return drafts


def _line_pieces(text: str, max_chars: int):
    """Yield ``(line_number, text)`` pieces, splitting overlong lines."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    for line_number, raw_line in enumerate(normalized.split("\n"), start=1):
        line = raw_line.rstrip()
        if not line:
            yield line_number, ""
            continue
        if len(line) <= max_chars:
            yield line_number, line
            continue
        # A single very long line (minified JS, one-line JSON) is split on
        # character boundaries; it keeps its line number for citations.
        for start in range(0, len(line), max_chars):
            yield line_number, line[start : start + max_chars]


def _overlap_tail(
    buffer: list[tuple[int, str]], overlap_chars: int
) -> list[tuple[int, str]]:
    if overlap_chars <= 0:
        return []
    tail: list[tuple[int, str]] = []
    total = 0
    for line_number, text in reversed(buffer):
        cost = len(text) + (1 if tail else 0)
        if total + cost > overlap_chars:
            break
        tail.insert(0, (line_number, text))
        total += cost
    return tail


def _draft(index: int, buffer: list[tuple[int, str]]) -> ChunkDraft:
    return ChunkDraft(
        index=index,
        text="\n".join(text for _, text in buffer).strip("\n"),
        start_line=buffer[0][0],
        end_line=buffer[-1][0],
    )


__all__ = ["ChunkDraft", "chunk_segments", "chunk_text"]
