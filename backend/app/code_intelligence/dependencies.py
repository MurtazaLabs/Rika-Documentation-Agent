"""Import graphs and lightweight relationship edges.

Dependencies are stored exactly as written in the source (``app.core.config``,
``./utils``, ``System.Linq``) so a later phase can resolve them to documents
inside the same project. Extraction is intentionally tolerant: a grammar that
does not expose a field still falls back to the node's text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.code_intelligence.tree_sitter import (
    child_text,
    line_range,
    text_of,
)


@dataclass(slots=True)
class Dependency:
    target_reference: str
    dependency_type: str
    start_line: int
    end_line: int
    metadata: dict[str, Any] = field(default_factory=dict)


def extract_dependencies(language: str, tree: Any, source: str) -> list[Dependency]:
    """Collect import/include/require edges from a parsed tree."""
    language = "bash" if language == "shell" else language
    if language in {"vue", "svelte"}:
        return _embedded_script_dependencies(tree, source)

    found: list[tuple[str, str, Any]] = []
    _walk(tree.root_node, language, found)

    dependencies: list[Dependency] = []
    seen: set[tuple[str, str]] = set()
    for target, dependency_type, node in found:
        target = target.strip().strip(";").strip()
        if not target:
            continue
        key = (target, dependency_type)
        if key in seen:
            continue
        seen.add(key)
        start, end = line_range(node)
        dependencies.append(
            Dependency(
                target_reference=target[:512],
                dependency_type=dependency_type,
                start_line=start,
                end_line=end,
                metadata={"language": language},
            )
        )
    return dependencies


def _walk(node: Any, language: str, found: list[tuple[str, str, Any]]) -> None:
    node_type = node.type

    handler = _HANDLERS.get((language, node_type))
    if handler is not None:
        handler(node, found)
        # Most import nodes contain no nested imports. Still descend, because
        # some languages wrap imports in a declaration list.
    elif language in {"javascript", "typescript"} and node_type == "call_expression":
        target = _js_require(node)
        if target:
            found.append((target, "import", node))
    elif language == "php" and node_type.endswith("_expression"):
        target = _php_require(node)
        if target:
            found.append((target, "require", node))
    elif language == "ruby" and node_type == "call":
        target = _ruby_require(node)
        if target:
            found.append((target, "require", node))
    elif language == "bash" and node_type == "command":
        target = _bash_source(node)
        if target:
            found.append((target, "source", node))
    elif language == "powershell" and node_type == "command":
        target = _powershell_import(node)
        if target:
            found.append((target, "import", node))
    elif language == "sql" and node_type in {"create_view", "create_table", "create_index"}:
        _sql_references(node, found)

    for child in node.named_children:
        _walk(child, language, found)


def _python_import(node: Any, found: list[tuple[str, str, Any]]) -> None:
    targets: list[str] = []
    for child in node.named_children:
        if child.type in {"dotted_name", "aliased_import"}:
            value = text_of(child).split(" as ")[0].strip()
            if value:
                targets.append(value)
    for target in targets:
        found.append((target, "import", node))


def _python_from_import(node: Any, found: list[tuple[str, str, Any]]) -> None:
    module = node.child_by_field_name("module_name")
    if module is not None:
        target = text_of(module).strip()
        if target:
            found.append((target, "import", node))
    elif node.type == "future_import_statement":
        found.append(("__future__", "import", node))


def _js_import(node: Any, found: list[tuple[str, str, Any]]) -> None:
    source = child_text(node, "source")
    if source:
        found.append((_unquote(source), "import", node))


def _js_require(node: Any) -> str | None:
    function = node.child_by_field_name("function")
    if function is None:
        return None
    name = text_of(function).strip()
    if name not in {"require", "import"}:
        return None
    arguments = node.child_by_field_name("arguments")
    if arguments is None:
        return None
    return _first_string(text_of(arguments))


def _java_import(node: Any, found: list[tuple[str, str, Any]]) -> None:
    text = text_of(node).strip().rstrip(";")
    text = re.sub(r"^import\s+(?:static\s+)?", "", text)
    if text:
        found.append((text, "import", node))


def _c_include(node: Any, found: list[tuple[str, str, Any]]) -> None:
    path = child_text(node, "path")
    if path:
        found.append((path.strip("<>\" "), "include", node))


def _csharp_using(node: Any, found: list[tuple[str, str, Any]]) -> None:
    text = text_of(node).strip().rstrip(";")
    text = re.sub(r"^using\s+(?:static\s+)?", "", text)
    if "=" in text:
        text = text.split("=", 1)[1].strip()
    if text:
        found.append((text, "using", node))


def _go_import(node: Any, found: list[tuple[str, str, Any]]) -> None:
    path = child_text(node, "path")
    if path:
        found.append((_unquote(path), "import", node))


def _rust_use(node: Any, found: list[tuple[str, str, Any]]) -> None:
    argument = child_text(node, "argument") or text_of(node)
    target = argument.strip().rstrip(";")
    target = re.sub(r"^use\s+", "", target)
    if "{" in target:
        target = target.split("{", 1)[0].rstrip(":").strip()
    target = target.split(" as ")[0].strip()
    if target:
        found.append((target, "import", node))


def _rust_mod(node: Any, found: list[tuple[str, str, Any]]) -> None:
    if node.child_by_field_name("body") is None:
        name = child_text(node, "name")
        if name:
            found.append((name, "module", node))


def _php_use(node: Any, found: list[tuple[str, str, Any]]) -> None:
    for child in node.named_children:
        if child.type == "namespace_use_clause":
            qualified = next(
                (
                    item
                    for item in child.named_children
                    if item.type in {"qualified_name", "name"}
                ),
                None,
            )
            if qualified is not None:
                target = text_of(qualified).strip().lstrip("\\")
                if target:
                    found.append((target, "import", node))


def _php_require(node: Any) -> str | None:
    match = re.search(
        r"\b(?:require|require_once|include|include_once)\b\s*\(?\s*[\"']([^\"']+)[\"']",
        text_of(node),
    )
    return match.group(1) if match else None


def _ruby_require(node: Any) -> str | None:
    method = child_text(node, "method")
    if method not in {"require", "require_relative", "load"}:
        return None
    arguments = node.child_by_field_name("arguments")
    if arguments is None:
        return None
    return _first_string(text_of(arguments))


def _kotlin_import(node: Any, found: list[tuple[str, str, Any]]) -> None:
    text = text_of(node).strip()
    text = re.sub(r"^import\s+", "", text)
    text = text.split(" as ")[0].strip()
    if text:
        found.append((text, "import", node))


def _swift_import(node: Any, found: list[tuple[str, str, Any]]) -> None:
    text = text_of(node).strip()
    text = re.sub(r"^(?:@testable\s+)?import\s+", "", text)
    if text:
        found.append((text, "import", node))


def _bash_source(node: Any) -> str | None:
    text = text_of(node).strip()
    match = re.match(r"^(?:source|\.)\s+([^\s;]+)", text)
    if match:
        return _unquote(match.group(1))
    return None


def _powershell_import(node: Any) -> str | None:
    text = text_of(node).strip()
    match = re.match(r"^Import-Module\s+([^\s;]+)", text, re.IGNORECASE)
    if match:
        return _unquote(match.group(1))
    return None


def _css_import(node: Any, found: list[tuple[str, str, Any]]) -> None:
    text = text_of(node)
    match = re.search(r"@import\s+(?:url\()?\s*[\"']?([^\"')\s;]+)", text)
    if match:
        found.append((match.group(1), "import", node))


def _sql_references(node: Any, found: list[tuple[str, str, Any]]) -> None:
    references = list(_descendants(node, {"object_reference"}))
    if node.type in {"create_view", "create_table", "create_index"}:
        # The first object_reference is usually the definition itself.
        if references and node.type == "create_view":
            references = references[1:]
        elif references and node.type == "create_table":
            references = references[1:]
        elif node.type == "create_index":
            references = references
    for reference in references:
        value = text_of(reference).strip()
        if value:
            found.append((value, "references", node))


def _embedded_script_dependencies(tree: Any, source: str) -> list[Dependency]:
    """Parse Vue/Svelte ``<script>`` blocks with the TypeScript grammar."""
    from app.code_intelligence.tree_sitter import parse_source

    dependencies: list[Dependency] = []
    seen: set[tuple[str, str]] = set()
    for script in _descendants(tree.root_node, {"script_element"}):
        raw = next(
            (child for child in script.named_children if child.type == "raw_text"),
            None,
        )
        if raw is None:
            continue
        script_source = text_of(raw)
        try:
            _, script_tree = parse_source("typescript", script_source)
        except Exception:  # noqa: BLE001 - script may be plain JavaScript
            continue
        offset = raw.start_point[0]
        for dependency in extract_dependencies(
            "typescript", script_tree, script_source
        ):
            key = (dependency.target_reference, dependency.dependency_type)
            if key in seen:
                continue
            seen.add(key)
            dependency.start_line += offset
            dependency.end_line += offset
            dependencies.append(dependency)
    return dependencies


def _descendants(node: Any, types: set[str]):
    stack = list(node.named_children)
    while stack:
        child = stack.pop(0)
        if child.type in types:
            yield child
        stack = list(child.named_children) + stack


def _first_string(text: str) -> str:
    match = re.search(r"[\"'`]([^\"'`]*)[\"'`]", text)
    return match.group(1) if match else ""


def _unquote(text: str) -> str:
    return text.strip().strip("'\"`")


_HANDLERS = {
    ("python", "import_statement"): _python_import,
    ("python", "import_from_statement"): _python_from_import,
    ("python", "future_import_statement"): _python_from_import,
    ("javascript", "import_statement"): _js_import,
    ("typescript", "import_statement"): _js_import,
    ("java", "import_declaration"): _java_import,
    ("c", "preproc_include"): _c_include,
    ("cpp", "preproc_include"): _c_include,
    ("csharp", "using_directive"): _csharp_using,
    ("go", "import_spec"): _go_import,
    ("rust", "use_declaration"): _rust_use,
    ("rust", "mod_item"): _rust_mod,
    ("php", "namespace_use_declaration"): _php_use,
    ("kotlin", "import_header"): _kotlin_import,
    ("swift", "import_declaration"): _swift_import,
    ("css", "import_statement"): _css_import,
}


__all__ = ["Dependency", "extract_dependencies"]
