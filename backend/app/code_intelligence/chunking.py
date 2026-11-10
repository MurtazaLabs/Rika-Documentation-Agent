"""Symbol-aware code chunking.

Small files stay in one piece. Larger files are cut on top-level definition
boundaries, so a function or class is normally a single chunk. An oversized
container is split into its header, complete child symbols, and the gaps
between them; an oversized function is split by lines and every part keeps the
same symbol name. Line ranges always refer to the original file.
"""

from __future__ import annotations

from typing import Any

from app.code_intelligence import CodeAnalysis, Symbol
from app.ingestion.chunking import ChunkDraft, chunk_text

_NOT_CHUNK_BOUNDARIES = {"route", "constant", "property"}


def chunk_code(
    source: str,
    analysis: CodeAnalysis,
    *,
    max_chars: int = 1200,
    overlap_chars: int = 200,
) -> list[ChunkDraft]:
    """Chunk source code using its extracted symbol ranges."""
    if max_chars < 1:
        raise ValueError("max_chars must be positive")
    if overlap_chars < 0:
        raise ValueError("overlap_chars cannot be negative")

    normalized = source.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    if not any(line.strip() for line in lines):
        return []

    imports = [
        dependency.target_reference
        for dependency in analysis.dependencies
        if dependency.target_reference
    ]
    imports = list(dict.fromkeys(imports))
    base_metadata: dict[str, Any] = {
        "language": analysis.language,
        "grammar": analysis.grammar,
    }
    if imports:
        base_metadata["imports"] = imports

    definitions = [
        symbol
        for symbol in analysis.symbols
        if symbol.tree_parent is None and _is_chunkable(symbol)
    ]
    definitions.sort(key=lambda item: (item.start_line, item.end_line))

    if len(source) <= max_chars:
        metadata = dict(base_metadata)
        if definitions:
            metadata["symbols"] = [symbol.name for symbol in definitions]
        symbol_name = definitions[0].name if len(definitions) == 1 else None
        return [
            ChunkDraft(
                index=0,
                text=source.strip("\n"),
                start_line=1,
                end_line=max(len(lines), 1),
                symbol_name=symbol_name,
                metadata=metadata,
            )
        ]

    builder = _Builder(lines, analysis, base_metadata, max_chars, overlap_chars)
    if not definitions:
        builder.gap(1, len(lines))
        return builder.finish() or _fallback(
            normalized, base_metadata, max_chars, overlap_chars
        )

    cursor = 1
    for symbol in definitions:
        start = max(symbol.start_line, 1)
        end = min(symbol.end_line, len(lines))
        if end < start:
            continue
        if start > cursor:
            builder.gap(cursor, start - 1)
        builder.symbol(symbol, end=end)
        cursor = max(cursor, end + 1)
    if cursor <= len(lines):
        builder.gap(cursor, len(lines))

    return builder.finish() or _fallback(
        normalized, base_metadata, max_chars, overlap_chars
    )


class _Builder:
    def __init__(
        self,
        lines: list[str],
        analysis: CodeAnalysis,
        base_metadata: dict[str, Any],
        max_chars: int,
        overlap_chars: int,
    ) -> None:
        self.lines = lines
        self.analysis = analysis
        self.base_metadata = base_metadata
        self.max_chars = max_chars
        self.overlap_chars = overlap_chars
        self.drafts: list[ChunkDraft] = []

    def finish(self) -> list[ChunkDraft]:
        for index, draft in enumerate(self.drafts):
            draft.index = index
        return [draft for draft in self.drafts if draft.text.strip()]

    def gap(
        self,
        start: int,
        end: int,
        *,
        parent_symbol: str | None = None,
    ) -> None:
        metadata = dict(self.base_metadata)
        if parent_symbol:
            metadata["parent_symbol"] = parent_symbol
        self._range(start, end, symbol_name=None, metadata=metadata)

    def symbol(self, symbol: Symbol, *, end: int | None = None) -> None:
        start = max(symbol.start_line, 1)
        finish = min(end if end is not None else symbol.end_line, len(self.lines))
        if finish < start:
            return
        text = self._slice(start, finish)
        if len(text) <= self.max_chars:
            metadata = self._symbol_metadata(symbol)
            self._add(text, start, finish, symbol.name, metadata)
            return

        children = [
            child
            for child in self.analysis.symbols
            if child.tree_parent == symbol.qualified_name
            and _is_chunkable(child)
            and start <= child.start_line
            and child.end_line <= finish
        ]
        children.sort(key=lambda item: (item.start_line, item.end_line))

        if _is_container(symbol.symbol_type) and children:
            self._container(symbol, start, finish, children)
            return

        metadata = self._symbol_metadata(symbol)
        self._split(start, finish, symbol.name, metadata, part=True)

    def _container(
        self,
        symbol: Symbol,
        start: int,
        finish: int,
        children: list[Symbol],
    ) -> None:
        header_end = min(children[0].start_line - 1, finish)
        if header_end >= start:
            metadata = self._symbol_metadata(symbol)
            metadata["symbol_part"] = "header"
            self._split(start, header_end, symbol.name, metadata, part=False)
        cursor = max(header_end + 1, start)
        for child in children:
            child_start = max(child.start_line, start)
            child_end = min(child.end_line, finish)
            if child_end < child_start:
                continue
            if child_start > cursor:
                self.gap(
                    cursor,
                    child_start - 1,
                    parent_symbol=symbol.qualified_name,
                )
            self.symbol(child, end=child_end)
            cursor = max(cursor, child_end + 1)
        if cursor <= finish:
            metadata = self._symbol_metadata(symbol)
            metadata["symbol_part"] = "tail"
            self._split(cursor, finish, symbol.name, metadata, part=False)

    def _symbol_metadata(self, symbol: Symbol) -> dict[str, Any]:
        metadata = dict(self.base_metadata)
        metadata.update(
            {
                "symbol_type": symbol.symbol_type,
                "symbol_start_line": symbol.start_line,
                "symbol_end_line": symbol.end_line,
            }
        )
        if symbol.parent:
            metadata["parent_symbol"] = symbol.parent
        if symbol.metadata.get("signature"):
            metadata["signature"] = symbol.metadata["signature"]
        if symbol.metadata.get("routes"):
            metadata["routes"] = symbol.metadata["routes"]
        return metadata

    def _split(
        self,
        start: int,
        end: int,
        symbol_name: str | None,
        metadata: dict[str, Any],
        *,
        part: bool,
    ) -> None:
        text = self._slice(start, end)
        if not text.strip():
            return
        if len(text) <= self.max_chars:
            self._add(text, start, end, symbol_name, metadata)
            return
        for local in chunk_text(
            text, max_chars=self.max_chars, overlap_chars=self.overlap_chars
        ):
            chunk_metadata = dict(metadata)
            if part:
                chunk_metadata["symbol_part"] = "part"
            self._add(
                local.text,
                start + local.start_line - 1,
                start + local.end_line - 1,
                symbol_name,
                chunk_metadata,
            )

    def _range(
        self,
        start: int,
        end: int,
        *,
        symbol_name: str | None,
        metadata: dict[str, Any],
    ) -> None:
        if end < start:
            return
        text = self._slice(start, end)
        if not text.strip():
            return
        if len(text) <= self.max_chars:
            self._add(text, start, end, symbol_name, metadata)
            return
        for local in chunk_text(
            text, max_chars=self.max_chars, overlap_chars=self.overlap_chars
        ):
            self._add(
                local.text,
                start + local.start_line - 1,
                start + local.end_line - 1,
                symbol_name,
                dict(metadata),
            )

    def _add(
        self,
        text: str,
        start: int,
        end: int,
        symbol_name: str | None,
        metadata: dict[str, Any],
    ) -> None:
        if not text.strip():
            return
        self.drafts.append(
            ChunkDraft(
                index=len(self.drafts),
                text=text.strip("\n"),
                start_line=start,
                end_line=end,
                symbol_name=symbol_name,
                metadata=dict(metadata),
            )
        )

    def _slice(self, start: int, end: int) -> str:
        start = max(start, 1)
        end = min(end, len(self.lines))
        return "\n".join(self.lines[start - 1 : end])


def _is_chunkable(symbol: Symbol) -> bool:
    return symbol.symbol_type not in _NOT_CHUNK_BOUNDARIES


def _is_container(symbol_type: str) -> bool:
    return symbol_type in {
        "class",
        "interface",
        "struct",
        "trait",
        "enum",
        "union",
        "module",
        "namespace",
        "object",
        "extension",
        "impl",
        "type",
    }


def _fallback(
    source: str,
    base_metadata: dict[str, Any],
    max_chars: int,
    overlap_chars: int,
) -> list[ChunkDraft]:
    drafts = chunk_text(source, max_chars=max_chars, overlap_chars=overlap_chars)
    for draft in drafts:
        draft.metadata.update(base_metadata)
    return drafts


__all__ = ["chunk_code"]
