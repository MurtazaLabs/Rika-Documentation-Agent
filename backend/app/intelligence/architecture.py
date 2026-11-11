"""§13.2 architecture: layers, their import edges, tables and request flows.

Layer membership comes from the path (``layers.layer_for``), edges from resolved
internal imports, tables from the model declarations ingestion already indexed,
and request flows from the route symbols the extractor emits for supported
frameworks. A flow lists the handler plus the modules its file imports, which is
as far as static analysis can honestly go without executing code.
"""

from __future__ import annotations

import re

from app.intelligence.facts import FileFacts, ModuleResolver, ProjectFacts
from app.intelligence.layers import layer_for

_TABLE = re.compile(r"__tablename__\s*=\s*[\"']([A-Za-z_][\w]*)['\"]")
_MAPPED_COLUMN = re.compile(r"^\s{4,}([a-z_][\w]*)\s*:\s*Mapped\[", re.MULTILINE)
_ASSIGNED_COLUMN = re.compile(
    r"^\s{4,}([a-z_][\w]*)\s*=\s*(?:mapped_column|Column|models\.[A-Z]\w*Field)\(",
    re.MULTILINE,
)
_FOREIGN_KEY = re.compile(r"ForeignKey\(\s*[\"']([\w.]+)['\"]")
_MAX_FLOW_IMPORTS = 6


def architecture(facts: ProjectFacts) -> dict:
    resolver = ModuleResolver(facts.files)
    return {
        "project_id": facts.project_id,
        "layers": _layers(facts, resolver),
        "edges": _edges(facts, resolver),
        "database": {"tables": tables(facts)},
        "request_flows": request_flows(facts, resolver),
        "responsibilities": _responsibilities(facts),
    }


def _layers(facts: ProjectFacts, resolver: ModuleResolver) -> list[dict]:
    entries: dict[str, dict] = {}
    for file in facts.files:
        layer, side = layer_for(file.path)
        entry = entries.setdefault(
            layer,
            {
                "name": layer,
                "side": side,
                "files": 0,
                "symbols": 0,
                "imports_out": 0,
                "imported_by": 0,
            },
        )
        entry["files"] += 1
        entry["symbols"] += len(file.symbols)
        entry["imports_out"] += sum(
            1
            for item in file.imports
            if resolver.resolve(file, item.reference) not in (None, file.path)
        )

    for file in facts.files:
        source_layer = layer_for(file.path)[0]
        for item in file.imports:
            target = resolver.resolve(file, item.reference)
            if target is None or target == file.path:
                continue
            target_layer = layer_for(target)[0]
            if target_layer != source_layer:
                entries[target_layer]["imported_by"] += 1

    return sorted(entries.values(), key=lambda item: (-item["files"], item["name"]))


def _edges(facts: ProjectFacts, resolver: ModuleResolver) -> list[dict]:
    counts: dict[tuple[str, str], int] = {}
    for file in facts.files:
        source = layer_for(file.path)[0]
        for item in file.imports:
            target = resolver.resolve(file, item.reference)
            if target is None or target == file.path:
                continue
            destination = layer_for(target)[0]
            if destination == source:
                continue
            counts[(source, destination)] = counts.get((source, destination), 0) + 1

    return [
        {"source": source, "target": target, "count": count}
        for (source, target), count in sorted(
            counts.items(), key=lambda item: (-item[1], item[0])
        )
    ]


def tables(facts: ProjectFacts) -> list[dict]:
    """ORM tables declared in the project, with columns and foreign-key targets."""
    found: list[dict] = []
    for file in facts.code_files:
        if "__tablename__" not in file.text:
            continue
        for match in _TABLE.finditer(file.text):
            table = match.group(1)
            line = _line_at(file.text, match.start())
            model = _enclosing_class(file, line)
            body = _class_body(file.text, line)
            columns = sorted(
                set(_MAPPED_COLUMN.findall(body)) | set(_ASSIGNED_COLUMN.findall(body))
            )
            references = sorted(
                {target.split(".", 1)[0] for target in _FOREIGN_KEY.findall(body)}
            )
            found.append(
                {
                    "table": table,
                    "model": model,
                    "file_path": file.path,
                    "line": line,
                    "columns": columns,
                    "references": references,
                }
            )
    return sorted(found, key=lambda item: item["table"])


def request_flows(facts: ProjectFacts, resolver: ModuleResolver) -> list[dict]:
    flows: list[dict] = []
    for file in facts.code_files:
        # FastAPI keeps the mount point on the router, while the extractor sees
        # only the decorator path; without this the flows would all be "".
        prefix = _router_prefix(file.text)
        for symbol in file.symbols:
            if symbol.symbol_type != "route":
                continue
            metadata = symbol.metadata
            handler_file = file.path
            imports = []
            for item in file.imports:
                target = resolver.resolve(file, item.reference)
                if target and target != handler_file and target not in imports:
                    imports.append(target)
            flows.append(
                {
                    "method": str(metadata.get("http_method") or "ANY").upper(),
                    "path": _join_route(prefix, str(metadata.get("path") or "")),
                    "handler": str(metadata.get("handler") or symbol.parent or symbol.name),
                    "file_path": handler_file,
                    "line": symbol.start_line,
                    "framework": metadata.get("framework"),
                    "imports": imports[:_MAX_FLOW_IMPORTS],
                }
            )
    return sorted(flows, key=lambda item: (item["path"], item["method"]))


def _router_prefix(text: str) -> str:
    match = re.search(r"APIRouter\(\s*prefix\s*=\s*[\"']([^\"']*)[\"']", text)
    return match.group(1) if match else ""


def _join_route(prefix: str, path: str) -> str:
    joined = "/" + "/".join(part.strip("/") for part in (prefix, path) if part.strip("/"))
    return joined if joined != "/" else "/"


def _responsibilities(facts: ProjectFacts) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for file in facts.code_files:
        layer, side = layer_for(file.path)
        doc = _file_doc(file)
        grouped.setdefault(layer, []).append(
            {"path": file.path, "doc": doc, "symbols": len(file.symbols), "side": side}
        )

    result: list[dict] = []
    for layer, modules in grouped.items():
        modules.sort(key=lambda item: (-item["symbols"], item["path"]))
        result.append(
            {
                "layer": layer,
                "side": modules[0]["side"],
                "modules": modules[:5],
            }
        )
    return sorted(result, key=lambda item: (-len(item["modules"]), item["layer"]))


def _file_doc(file: FileFacts) -> str | None:
    """The module docstring, taken from the first documented symbol."""
    for symbol in file.symbols:
        if symbol.doc:
            return " ".join(symbol.doc.split())[:240]
    return None


def _line_at(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _enclosing_class(file: FileFacts, line: int) -> str | None:
    candidates = [
        symbol
        for symbol in file.symbols
        if symbol.symbol_type in {"class", "struct", "interface"}
        and symbol.start_line <= line <= symbol.end_line
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda symbol: symbol.end_line - symbol.start_line).name


def _class_body(text: str, start_line: int) -> str:
    """Text of the class that starts at or before ``start_line``."""
    lines = text.splitlines()
    index = max(0, start_line - 1)
    # Walk back to the class statement the tablename belongs to.
    while index > 0 and not lines[index].lstrip().startswith(("class ", "struct ", "public class")):
        index -= 1
    body: list[str] = []
    for line in lines[index:]:
        if body and line and not line.startswith((" ", "\t")):
            break
        body.append(line)
        if len(body) > 400:
            break
    return "\n".join(body)
