"""Tree-sitter parser access and small node helpers.

Grammars come from ``tree-sitter-language-pack``, whose Windows wheel bundles
the languages Rika targets, so indexing never needs a network download. A
parser is cached per thread: worker threads and Celery tasks must not share a
mutable parser instance.
"""

from __future__ import annotations

import threading
from pathlib import PurePosixPath
from typing import Any

# The language stored on a document is the human-facing name; these are the
# grammar names used by tree-sitter-language-pack.
GRAMMAR_BY_LANGUAGE: dict[str, str] = {
    "python": "python",
    "javascript": "javascript",
    "typescript": "typescript",
    "java": "java",
    "kotlin": "kotlin",
    "swift": "swift",
    "go": "go",
    "rust": "rust",
    "ruby": "ruby",
    "php": "php",
    "csharp": "csharp",
    "c": "c",
    "cpp": "cpp",
    "sql": "sql",
    "css": "css",
    "shell": "bash",
    "bash": "bash",
    "powershell": "powershell",
    "vue": "vue",
    "svelte": "svelte",
}

EXTENSION_GRAMMAR: dict[str, str] = {
    ".tsx": "tsx",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".pyi": "python",
    ".h": "c",
    ".hh": "cpp",
    ".hpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".kts": "kotlin",
    ".psm1": "powershell",
    ".bash": "bash",
    ".zsh": "bash",
    ".scss": "css",
    ".sass": "css",
    ".less": "css",
}

_local = threading.local()


class CodeIntelligenceError(Exception):
    """A source file could not be parsed for structural analysis."""


def grammar_for(language: str | None, filename: str | None = None) -> str | None:
    """Resolve a format language (and extension) to a bundled grammar name."""
    if not language:
        return None
    if filename:
        suffix = PurePosixPath(filename).suffix.lower()
        if suffix in EXTENSION_GRAMMAR:
            return EXTENSION_GRAMMAR[suffix]
    return GRAMMAR_BY_LANGUAGE.get(language.lower())


def _parser(grammar: str):
    parsers = getattr(_local, "parsers", None)
    if parsers is None:
        parsers = {}
        _local.parsers = parsers
    parser = parsers.get(grammar)
    if parser is None:
        from tree_sitter_language_pack import get_parser

        parser = get_parser(grammar)
        parsers[grammar] = parser
    return parser


def parse_source(
    language: str | None, source: str, filename: str | None = None
) -> tuple[str, Any]:
    """Parse ``source`` and return ``(grammar, tree)``."""
    grammar = grammar_for(language, filename)
    if grammar is None:
        raise CodeIntelligenceError(f"No Tree-sitter grammar for {language!r}")
    try:
        parser = _parser(grammar)
        tree = parser.parse(source.encode("utf-8"))
    except Exception as error:  # noqa: BLE001 - optional language packs vary
        raise CodeIntelligenceError(
            f"Tree-sitter could not parse the {language} file: {error}"
        ) from error
    if tree.root_node is None:  # pragma: no cover - defensive
        raise CodeIntelligenceError("Tree-sitter returned an empty syntax tree")
    return grammar, tree


def text_of(node: Any) -> str:
    value = node.text
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def line_range(node: Any) -> tuple[int, int]:
    """Return 1-based inclusive line numbers for a Tree-sitter node."""
    start_row, _ = node.start_point
    end_row, end_column = node.end_point
    start_line = start_row + 1
    end_line = end_row + 1
    # A node that ends at column 0 really ends on the previous line.
    if end_column == 0 and end_line > start_line:
        end_line -= 1
    return start_line, end_line


def first_line(node: Any, limit: int = 240) -> str:
    for line in text_of(node).splitlines():
        cleaned = " ".join(line.split())
        if cleaned:
            return cleaned[:limit]
    return ""


def child_text(node: Any, field: str) -> str | None:
    child = node.child_by_field_name(field)
    return text_of(child).strip() if child is not None else None


__all__ = [
    "CodeIntelligenceError",
    "EXTENSION_GRAMMAR",
    "GRAMMAR_BY_LANGUAGE",
    "child_text",
    "first_line",
    "grammar_for",
    "line_range",
    "parse_source",
    "text_of",
]
