"""Source-code intelligence.

One syntax-tree pass yields symbols (functions, methods, classes, interfaces,
types, constants and API routes) and import/dependency edges. The chunker then
uses the symbol ranges to keep functions and classes whole.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.code_intelligence.dependencies import Dependency, extract_dependencies
from app.code_intelligence.symbols import Symbol, extract_symbols
from app.code_intelligence.tree_sitter import CodeIntelligenceError, parse_source


@dataclass(slots=True)
class CodeAnalysis:
    language: str
    grammar: str | None = None
    symbols: list[Symbol] = field(default_factory=list)
    dependencies: list[Dependency] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def failed(self) -> bool:
        return self.grammar is None


def analyze_code(
    language: str | None,
    source: str,
    filename: str | None = None,
) -> CodeAnalysis:
    """Parse a source file and return its symbols and dependency edges.

    A missing or failing grammar degrades to a warning and an empty analysis;
    the caller still indexes the file as plain text. A syntax tree containing
    error nodes is accepted: Tree-sitter recovers and the ranges it reports
    remain useful for chunking.
    """
    analysis = CodeAnalysis(language=language or "unknown")
    if not source.strip():
        analysis.warnings.append("source file is empty")
        return analysis
    try:
        grammar, tree = parse_source(language, source, filename)
    except CodeIntelligenceError as error:
        analysis.warnings.append(str(error))
        return analysis

    analysis.grammar = grammar
    try:
        analysis.symbols = extract_symbols(language or "", tree, source)
    except Exception as error:  # noqa: BLE001 - analysis must not sink ingestion
        analysis.warnings.append(f"symbol extraction failed: {error}")
    try:
        analysis.dependencies = extract_dependencies(language or "", tree, source)
    except Exception as error:  # noqa: BLE001
        analysis.warnings.append(f"dependency extraction failed: {error}")
    if tree.root_node.has_error:
        analysis.warnings.append(
            "syntax errors were present; Tree-sitter recovered a partial tree"
        )
    return analysis


__all__ = [
    "CodeAnalysis",
    "Dependency",
    "Symbol",
    "analyze_code",
]
