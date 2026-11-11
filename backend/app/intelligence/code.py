"""§13.3 code analysis over the stored symbol graph.

Symbol search and explanations, endpoint discovery, import analysis and
reference lookup. ``symbol_detail`` says explicitly what it found in the index —
definition text, sibling symbols, importers and textual references — instead of
inventing a call graph that the parser never built.
"""

from __future__ import annotations

import re
import uuid

from app.intelligence.architecture import request_flows
from app.intelligence.facts import FileFacts, ModuleResolver, ProjectFacts, SymbolFact

_MAX_DEFINITION_LINES = 200
_MAX_REFERENCES = 25
_MAX_HITS = 100


def search_symbols(
    facts: ProjectFacts,
    *,
    query: str | None = None,
    symbol_type: str | None = None,
    path: str | None = None,
    limit: int = 50,
) -> list[dict]:
    needle = (query or "").strip().lower()
    hits: list[dict] = []
    for file in facts.code_files:
        if path and path not in file.path:
            continue
        for symbol in file.symbols:
            if symbol_type and symbol.symbol_type != symbol_type:
                continue
            if needle and needle not in symbol.name.lower() and needle not in symbol.qualified_name.lower():
                continue
            hits.append(_hit(file, symbol))
            if len(hits) >= min(limit, _MAX_HITS):
                return _sorted(hits, needle)
    return _sorted(hits, needle)


def symbol_detail(facts: ProjectFacts, symbol_id: uuid.UUID) -> dict | None:
    for file in facts.files:
        for symbol in file.symbols:
            if symbol.id == symbol_id:
                return _detail(facts, file, symbol)
    return None


def routes(facts: ProjectFacts, *, method: str | None = None) -> list[dict]:
    flows = request_flows(facts, ModuleResolver(facts.files))
    if method:
        wanted = method.upper()
        flows = [flow for flow in flows if flow["method"] == wanted]
    return flows


def import_analysis(facts: ProjectFacts, path: str) -> dict | None:
    file = facts.by_path(path)
    if file is None or not file.is_code:
        return None
    resolver = ModuleResolver(facts.files)
    imports = []
    for item in file.imports:
        target = resolver.resolve(file, item.reference)
        imports.append(
            {
                "reference": item.reference,
                "dependency_type": item.dependency_type,
                "resolved_path": target,
                "external": target is None and not resolver.looks_internal(item.reference),
            }
        )
    imported_by = [
        other.path
        for other in facts.code_files
        if other.path != path
        and any(resolver.resolve(other, item.reference) == path for item in other.imports)
    ]
    return {
        "path": file.path,
        "imports": imports,
        "imported_by": imported_by,
        "symbols": [_hit(file, symbol) for symbol in file.symbols],
    }


def _detail(facts: ProjectFacts, file: FileFacts, symbol: SymbolFact) -> dict:
    resolver = ModuleResolver(facts.files)
    definition = file.slice_lines(symbol.start_line, min(symbol.end_line, symbol.start_line + _MAX_DEFINITION_LINES))
    related = [
        _hit(file, other)
        for other in file.symbols
        if other.id != symbol.id
        and (
            other.parent == symbol.qualified_name
            or (symbol.parent is not None and other.qualified_name == symbol.parent)
        )
    ]
    return {
        "symbol": _hit(file, symbol),
        "doc": symbol.doc,
        "signature": symbol.signature,
        "definition": definition,
        "imports": [
            {
                "reference": item.reference,
                "resolved_path": resolver.resolve(file, item.reference),
            }
            for item in file.imports
        ],
        "imported_by": [
            other.path
            for other in facts.code_files
            if other.path != file.path
            and any(resolver.resolve(other, item.reference) == file.path for item in other.imports)
        ],
        "related_symbols": related[:20],
        "references": _references(facts, file, symbol),
    }


def _references(facts: ProjectFacts, file: FileFacts, symbol: SymbolFact) -> list[dict]:
    """Textual usages of the symbol's name outside its own definition.

    This is a lexical lookup, not a resolved call graph; the report labels it as
    such so a mention is never presented as a proven call site.
    """
    if symbol.symbol_type == "route" or len(symbol.name) < 3:
        return []
    pattern = re.compile(rf"\b{re.escape(symbol.name)}\b")
    found: list[dict] = []
    for other in facts.code_files:
        same_file = other.path == file.path
        for number, line in enumerate(other.lines, start=1):
            if same_file and symbol.start_line <= number <= symbol.end_line:
                continue
            if not pattern.search(line):
                continue
            found.append(
                {
                    "path": other.path,
                    "line": number,
                    "snippet": line.strip()[:200],
                }
            )
            if len(found) >= _MAX_REFERENCES:
                return found
    return found


def _hit(file: FileFacts, symbol: SymbolFact) -> dict:
    return {
        "id": symbol.id,
        "name": symbol.name,
        "qualified_name": symbol.qualified_name,
        "symbol_type": symbol.symbol_type,
        "path": file.path,
        "language": file.language,
        "start_line": symbol.start_line,
        "end_line": symbol.end_line,
        "signature": symbol.signature,
        "doc": symbol.doc,
    }


def _sorted(hits: list[dict], needle: str) -> list[dict]:
    def key(hit: dict) -> tuple:
        name = hit["name"].lower()
        return (name != needle, not name.startswith(needle), hit["path"], hit["start_line"])

    return sorted(hits, key=key)
