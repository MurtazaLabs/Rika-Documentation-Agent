"""Structural symbols extracted from a Tree-sitter syntax tree.

The extractor keeps two kinds of parent information:

* ``parent`` is the logical scope (a method's class, a Go method's receiver,
  a Rust method's impl type). It is what a reader means by "parent scope".
* ``tree_parent`` is the enclosing symbol in the syntax tree. It is what the
  chunker needs: Go methods and Rust ``impl`` methods sit at the top level of
  the file even though their logical parent is a type.

Route declarations are emitted as their own symbols (``symbol_type="route"``)
and are also summarized on the handler's metadata. They never become chunk
boundaries; the handler chunk already contains its decorator/annotation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.code_intelligence.tree_sitter import (
    child_text,
    first_line,
    line_range,
    text_of,
)


@dataclass(slots=True)
class Symbol:
    name: str
    symbol_type: str
    start_line: int
    end_line: int
    qualified_name: str
    parent: str | None = None
    tree_parent: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SymbolRule:
    symbol_type: str
    name_field: str | None = None
    name_types: tuple[str, ...] = ()
    container: bool = False
    method_if_parent: bool = False
    recurse: bool = True


_METHOD_PARENT_TYPES = {
    "class",
    "interface",
    "struct",
    "trait",
    "module",
    "namespace",
    "object",
    "extension",
    "impl",
}

_CONTAINER_TYPES = _METHOD_PARENT_TYPES | {
    "enum",
    "union",
    "type",
    "record",
}

_HTTP_METHODS = {
    "get",
    "post",
    "put",
    "patch",
    "delete",
    "head",
    "options",
    "trace",
    "connect",
}

_PYTHON_RULES: dict[str, SymbolRule] = {
    "function_definition": SymbolRule(
        "function", name_field="name", method_if_parent=True
    ),
    "class_definition": SymbolRule(
        "class", name_field="name", container=True
    ),
}

_JS_RULES: dict[str, SymbolRule] = {
    "function_declaration": SymbolRule("function", name_field="name"),
    "generator_function_declaration": SymbolRule("function", name_field="name"),
    "class_declaration": SymbolRule("class", name_field="name", container=True),
    "method_definition": SymbolRule("method", name_field="name"),
}

_TS_RULES: dict[str, SymbolRule] = {
    **_JS_RULES,
    "interface_declaration": SymbolRule(
        "interface", name_field="name", container=True
    ),
    "type_alias_declaration": SymbolRule(
        "type", name_field="name", recurse=False
    ),
    "enum_declaration": SymbolRule(
        "enum", name_field="name", container=True
    ),
    "abstract_class_declaration": SymbolRule(
        "class", name_field="name", container=True
    ),
    "abstract_method_signature": SymbolRule("method", name_field="name"),
    "method_signature": SymbolRule("method", name_field="name"),
}

_JAVA_RULES: dict[str, SymbolRule] = {
    "class_declaration": SymbolRule("class", name_field="name", container=True),
    "interface_declaration": SymbolRule(
        "interface", name_field="name", container=True
    ),
    "enum_declaration": SymbolRule("enum", name_field="name", container=True),
    "record_declaration": SymbolRule("class", name_field="name", container=True),
    "annotation_type_declaration": SymbolRule(
        "interface", name_field="name", container=True
    ),
    "method_declaration": SymbolRule("method", name_field="name"),
    "constructor_declaration": SymbolRule("method", name_field="name"),
}

_CSHARP_RULES: dict[str, SymbolRule] = {
    "class_declaration": SymbolRule("class", name_field="name", container=True),
    "interface_declaration": SymbolRule(
        "interface", name_field="name", container=True
    ),
    "struct_declaration": SymbolRule("struct", name_field="name", container=True),
    "enum_declaration": SymbolRule("enum", name_field="name", container=True),
    "record_declaration": SymbolRule("class", name_field="name", container=True),
    "delegate_declaration": SymbolRule("type", name_field="name", recurse=False),
    "namespace_declaration": SymbolRule(
        "namespace", name_field="name", container=True
    ),
    "file_scoped_namespace_declaration": SymbolRule(
        "namespace", name_field="name", container=True
    ),
    "method_declaration": SymbolRule("method", name_field="name"),
    "constructor_declaration": SymbolRule("method", name_field="name"),
    "property_declaration": SymbolRule(
        "property", name_field="name", recurse=False
    ),
}

_GO_RULES: dict[str, SymbolRule] = {
    "function_declaration": SymbolRule("function", name_field="name"),
    "method_declaration": SymbolRule("method", name_field="name"),
    "method_elem": SymbolRule("method", name_field="name"),
}

_RUST_RULES: dict[str, SymbolRule] = {
    "function_item": SymbolRule("function", name_field="name", method_if_parent=True),
    "function_signature_item": SymbolRule(
        "method", name_field="name", method_if_parent=True
    ),
    "struct_item": SymbolRule("struct", name_field="name", container=True),
    "enum_item": SymbolRule("enum", name_field="name", container=True),
    "union_item": SymbolRule("union", name_field="name", container=True),
    "trait_item": SymbolRule("trait", name_field="name", container=True),
    "mod_item": SymbolRule("module", name_field="name", container=True),
    "type_item": SymbolRule("type", name_field="name", recurse=False),
    "const_item": SymbolRule("constant", name_field="name", recurse=False),
    "static_item": SymbolRule("constant", name_field="name", recurse=False),
    "macro_definition": SymbolRule("constant", name_field="name", recurse=False),
}

_PHP_RULES: dict[str, SymbolRule] = {
    "function_definition": SymbolRule("function", name_field="name"),
    "class_declaration": SymbolRule("class", name_field="name", container=True),
    "interface_declaration": SymbolRule(
        "interface", name_field="name", container=True
    ),
    "trait_declaration": SymbolRule("trait", name_field="name", container=True),
    "enum_declaration": SymbolRule("enum", name_field="name", container=True),
    "method_declaration": SymbolRule("method", name_field="name"),
}

_RUBY_RULES: dict[str, SymbolRule] = {
    "class": SymbolRule("class", name_field="name", container=True),
    "module": SymbolRule("module", name_field="name", container=True),
    "method": SymbolRule("method", name_field="name"),
    "singleton_method": SymbolRule("method", name_field="name"),
}

_KOTLIN_RULES: dict[str, SymbolRule] = {
    "class_declaration": SymbolRule(
        "class",
        name_types=("type_identifier",),
        container=True,
    ),
    "object_declaration": SymbolRule(
        "object",
        name_types=("type_identifier",),
        container=True,
    ),
    "function_declaration": SymbolRule(
        "function",
        name_types=("simple_identifier",),
        method_if_parent=True,
    ),
}

_SWIFT_RULES: dict[str, SymbolRule] = {
    "class_declaration": SymbolRule(
        "class", name_field="name", container=True
    ),
    "protocol_declaration": SymbolRule(
        "interface", name_field="name", container=True
    ),
    "function_declaration": SymbolRule(
        "function", name_field="name", method_if_parent=True
    ),
    "init_declaration": SymbolRule("method", name_field="name"),
    "protocol_function_declaration": SymbolRule(
        "method", name_field="name", method_if_parent=True
    ),
    "typealias_declaration": SymbolRule("type", name_field="name", recurse=False),
}

_BASH_RULES: dict[str, SymbolRule] = {
    "function_definition": SymbolRule("function", name_field="name"),
}

_POWERSHELL_RULES: dict[str, SymbolRule] = {
    "function_statement": SymbolRule(
        "function", name_types=("function_name",)
    ),
    "class_statement": SymbolRule(
        "class", name_types=("simple_name",), container=True
    ),
    "class_method_definition": SymbolRule(
        "method", name_types=("simple_name",)
    ),
}

_C_RULES: dict[str, SymbolRule] = {
    "function_definition": SymbolRule("function", method_if_parent=True),
    "struct_specifier": SymbolRule("struct", name_field="name", container=True),
    "union_specifier": SymbolRule("union", name_field="name", container=True),
    "enum_specifier": SymbolRule("enum", name_field="name", container=True),
}

_CPP_RULES: dict[str, SymbolRule] = {
    **_C_RULES,
    "class_specifier": SymbolRule("class", name_field="name", container=True),
    "namespace_definition": SymbolRule(
        "namespace", name_field="name", container=True
    ),
    "alias_declaration": SymbolRule("type", name_field="name", recurse=False),
}

_SQL_RULES: dict[str, SymbolRule] = {
    "create_table": SymbolRule("table", recurse=False),
    "create_view": SymbolRule("view", recurse=False),
    "create_function": SymbolRule("function", recurse=False),
    "create_index": SymbolRule("index", recurse=False),
    "create_type": SymbolRule("type", recurse=False),
    "create_schema": SymbolRule("schema", recurse=False),
    "create_trigger": SymbolRule("trigger", recurse=False),
    "create_sequence": SymbolRule("sequence", recurse=False),
}

RULES: dict[str, dict[str, SymbolRule]] = {
    "python": _PYTHON_RULES,
    "javascript": _JS_RULES,
    "typescript": _TS_RULES,
    "java": _JAVA_RULES,
    "csharp": _CSHARP_RULES,
    "go": _GO_RULES,
    "rust": _RUST_RULES,
    "php": _PHP_RULES,
    "ruby": _RUBY_RULES,
    "kotlin": _KOTLIN_RULES,
    "swift": _SWIFT_RULES,
    "bash": _BASH_RULES,
    "shell": _BASH_RULES,
    "powershell": _POWERSHELL_RULES,
    "c": _C_RULES,
    "cpp": _CPP_RULES,
    "sql": _SQL_RULES,
}

_ANNOTATION_METHODS = {
    "GetMapping": "GET",
    "PostMapping": "POST",
    "PutMapping": "PUT",
    "PatchMapping": "PATCH",
    "DeleteMapping": "DELETE",
    "RequestMapping": None,
    "Path": None,
}

_CSHARP_METHODS = {
    "HttpGet": "GET",
    "HttpPost": "POST",
    "HttpPut": "PUT",
    "HttpPatch": "PATCH",
    "HttpDelete": "DELETE",
    "HttpHead": "HEAD",
    "HttpOptions": "OPTIONS",
    "Route": None,
}

_NEST_METHODS = {
    "Get": "GET",
    "Post": "POST",
    "Put": "PUT",
    "Patch": "PATCH",
    "Delete": "DELETE",
    "Head": "HEAD",
    "Options": "OPTIONS",
    "All": "ALL",
}


def extract_symbols(language: str, tree: Any, source: str) -> list[Symbol]:
    """Extract definitions, constants and API routes from a parsed tree."""
    return _SymbolExtractor(language, source).extract(tree.root_node)


class _SymbolExtractor:
    def __init__(self, language: str, source: str) -> None:
        self.language = "bash" if language == "shell" else language
        self.source = source
        self.rules = RULES.get(self.language, {})
        self.symbols: list[Symbol] = []
        self._seen: set[tuple[str, str, int]] = set()
        self._route_seen: set[tuple[str, str, str]] = set()

    # -- traversal ---------------------------------------------------------

    def extract(self, root: Any) -> list[Symbol]:
        self.visit(root, None, None, tree_parent=None)
        if self.language in {"javascript", "typescript"}:
            self._extract_js_express_routes(root)
        elif self.language in {"vue", "svelte"}:
            self._extract_embedded_scripts(root)
        return self.symbols

    def _extract_embedded_scripts(self, root: Any) -> None:
        """Treat a Vue/Svelte ``<script>`` block as a TypeScript/JS file.

        Without this the outer component grammar exposes no symbols and a
        ``.vue`` file would be chunked as plain text.
        """
        from app.code_intelligence.tree_sitter import parse_source

        for script in _descendants(root, {"script_element"}):
            raw = next(
                (child for child in script.named_children if child.type == "raw_text"),
                None,
            )
            if raw is None:
                continue
            script_source = text_of(raw)
            try:
                _, script_tree = parse_source("typescript", script_source)
            except Exception:  # noqa: BLE001 - the block may be plain JavaScript
                continue
            offset = raw.start_point[0]
            for symbol in extract_symbols("typescript", script_tree, script_source):
                symbol.start_line += offset
                symbol.end_line += offset
                symbol.metadata["embedded_script"] = True
                self._add(symbol)

    def visit(
        self,
        node: Any,
        parent_name: str | None,
        parent_type: str | None,
        *,
        tree_parent: str | None,
        start_line: int | None = None,
        exported: bool = False,
        decorators: list[Any] | None = None,
        class_base: str | None = None,
    ) -> None:
        node_type = node.type

        if self._handle_special(
            node,
            node_type,
            parent_name,
            parent_type,
            tree_parent=tree_parent,
            start_line=start_line,
            exported=exported,
            decorators=decorators,
            class_base=class_base,
        ):
            return

        rule = self.rules.get(node_type)
        if rule is not None:
            self._add_declaration(
                node,
                rule,
                parent_name,
                parent_type,
                tree_parent=tree_parent,
                start_line=start_line,
                exported=exported,
                decorators=decorators,
                class_base=class_base,
            )
            return

        self._visit_children(
            node,
            parent_name,
            parent_type,
            tree_parent=tree_parent,
            exported=exported,
            decorators=decorators,
            class_base=class_base,
        )

    def _visit_children(
        self,
        node: Any,
        parent_name: str | None,
        parent_type: str | None,
        *,
        tree_parent: str | None,
        exported: bool = False,
        decorators: list[Any] | None = None,
        class_base: str | None = None,
    ) -> None:
        if self.language in {"typescript", "javascript"} and node.type == "class_body":
            self._visit_ts_class_body(
                node,
                parent_name,
                parent_type,
                tree_parent=tree_parent,
                exported=exported,
                class_base=class_base,
            )
            return
        for child in node.named_children:
            self.visit(
                child,
                parent_name,
                parent_type,
                tree_parent=tree_parent,
                exported=exported,
                class_base=class_base,
            )

    def _visit_ts_class_body(
        self,
        node: Any,
        parent_name: str | None,
        parent_type: str | None,
        *,
        tree_parent: str | None,
        exported: bool,
        class_base: str | None,
    ) -> None:
        pending: list[Any] = []
        for child in node.named_children:
            if child.type == "decorator":
                pending.append(child)
                continue
            self.visit(
                child,
                parent_name,
                parent_type,
                tree_parent=tree_parent,
                exported=exported,
                decorators=pending or None,
                class_base=class_base,
            )
            pending = []

    def _handle_special(
        self,
        node: Any,
        node_type: str,
        parent_name: str | None,
        parent_type: str | None,
        *,
        tree_parent: str | None,
        start_line: int | None,
        exported: bool,
        decorators: list[Any] | None,
        class_base: str | None,
    ) -> bool:
        language = self.language

        if language == "python":
            if node_type == "decorated_definition":
                definition = node.child_by_field_name("definition")
                found = [
                    child
                    for child in node.named_children
                    if child.type == "decorator"
                ]
                if definition is not None:
                    self.visit(
                        definition,
                        parent_name,
                        parent_type,
                        tree_parent=tree_parent,
                        start_line=start_line or line_range(node)[0],
                        exported=exported,
                        decorators=found,
                        class_base=class_base,
                    )
                return True
            if node_type == "assignment":
                self._python_assignment(node, parent_name, tree_parent=tree_parent)
                return True

        if language in {"javascript", "typescript"}:
            if node_type == "export_statement":
                declaration = node.child_by_field_name("declaration")
                found = [
                    child
                    for child in node.named_children
                    if child.type == "decorator"
                ]
                if declaration is not None:
                    self.visit(
                        declaration,
                        parent_name,
                        parent_type,
                        tree_parent=tree_parent,
                        start_line=line_range(node)[0],
                        exported=True,
                        decorators=found or decorators,
                        class_base=class_base,
                    )
                return True
            if node_type in {"lexical_declaration", "variable_declaration"}:
                self._js_variables(
                    node,
                    parent_name,
                    tree_parent=tree_parent,
                    start_line=start_line,
                    exported=exported,
                )
                return True

        if language == "cpp" and node_type == "template_declaration":
            declaration = next(
                (
                    child
                    for child in node.named_children
                    if child.type
                    in {
                        "function_definition",
                        "class_specifier",
                        "struct_specifier",
                        "union_specifier",
                        "enum_specifier",
                        "namespace_definition",
                        "alias_declaration",
                        "declaration",
                    }
                ),
                None,
            )
            if declaration is not None:
                self.visit(
                    declaration,
                    parent_name,
                    parent_type,
                    tree_parent=tree_parent,
                    start_line=line_range(node)[0],
                    exported=exported,
                    decorators=decorators,
                    class_base=class_base,
                )
            return True

        if language == "go":
            if node_type == "type_declaration":
                for child in node.named_children:
                    if child.type in {"type_spec", "type_alias"}:
                        self.visit(
                            child,
                            parent_name,
                            parent_type,
                            tree_parent=tree_parent,
                        )
                return True
            if node_type == "type_spec":
                self._go_type_spec(node, parent_name, tree_parent=tree_parent)
                return True
            if node_type == "type_alias":
                self._go_type_spec(node, parent_name, tree_parent=tree_parent)
                return True
            if node_type == "const_declaration":
                for child in node.named_children:
                    if child.type == "const_spec":
                        self._add_constant_node(
                            node=child,
                            parent_name=parent_name,
                            tree_parent=tree_parent,
                            start_line=start_line,
                        )
                return True

        if language in {"c", "cpp"}:
            if node_type in {"preproc_def", "preproc_function_def"}:
                self._add_constant_node(
                    node=node,
                    parent_name=parent_name,
                    tree_parent=tree_parent,
                    start_line=start_line,
                )
                return True
            if node_type == "type_definition":
                self._c_type_definition(
                    node, parent_name, tree_parent=tree_parent
                )
                return True
            if node_type == "field_declaration":
                self._c_field_constants(node, parent_name, tree_parent=tree_parent)
                return True
            if node_type == "declaration":
                self._c_declaration_constants(
                    node, parent_name, tree_parent=tree_parent
                )
                return True

        if language == "java" and node_type == "field_declaration":
            self._field_constants(node, parent_name, tree_parent=tree_parent)
            return True

        if language == "csharp" and node_type == "field_declaration":
            self._csharp_field_constants(
                node, parent_name, tree_parent=tree_parent
            )
            return True

        if language == "php" and node_type == "const_declaration":
            self._php_constants(node, parent_name, tree_parent=tree_parent)
            return True

        if language == "ruby" and node_type == "assignment":
            self._ruby_constant(node, parent_name, tree_parent=tree_parent)
            return True

        if language == "kotlin" and node_type == "property_declaration":
            self._kotlin_property(node, parent_name, tree_parent=tree_parent)
            return True

        if language == "swift" and node_type == "property_declaration":
            self._swift_property(node, parent_name, tree_parent=tree_parent)
            return True

        if language == "bash" and node_type == "variable_assignment":
            self._bash_constant(node, parent_name, tree_parent=tree_parent)
            return True

        if language == "powershell" and node_type == "assignment_expression":
            self._powershell_constant(node, parent_name, tree_parent=tree_parent)
            return True

        if language == "rust" and node_type == "impl_item":
            impl_type = child_text(node, "type") or ""
            impl_type = re.split(r"[<\s]", impl_type.strip())[0] or None
            self._visit_children(
                node,
                impl_type,
                "impl",
                tree_parent=tree_parent,
                class_base=class_base,
            )
            return True

        return False

    # -- declarations ------------------------------------------------------

    def _add_declaration(
        self,
        node: Any,
        rule: SymbolRule,
        parent_name: str | None,
        parent_type: str | None,
        *,
        tree_parent: str | None,
        start_line: int | None,
        exported: bool,
        decorators: list[Any] | None,
        class_base: str | None,
    ) -> None:
        if node.type in {
            "struct_specifier",
            "union_specifier",
            "enum_specifier",
            "class_specifier",
        } and node.child_by_field_name("body") is None:
            # A forward declaration or a type usage, not a definition.
            return
        name, qualifier = self._name(node, rule)
        if not name:
            return

        if qualifier and not parent_name:
            parent_name = qualifier
            parent_type = "class"

        if self.language == "go" and node.type == "method_declaration":
            receiver = _go_receiver_type(node)
            if receiver:
                parent_name = receiver
                parent_type = "struct"

        symbol_type = rule.symbol_type
        if rule.method_if_parent and parent_type in _METHOD_PARENT_TYPES:
            symbol_type = "method"
        symbol_type = self._override_type(node, symbol_type)

        all_decorators = list(decorators or [])
        all_decorators.extend(
            child for child in node.named_children if child.type == "decorator"
        )
        start, end = line_range(node)
        if start_line is not None:
            start = min(start, start_line)
        qualified = f"{parent_name}.{name}" if parent_name else name
        metadata = self._symbol_metadata(
            node,
            name,
            symbol_type,
            parent_name,
            exported=exported,
            decorators=all_decorators,
        )
        if qualifier:
            metadata["qualifier"] = qualifier

        symbol = Symbol(
            name=name,
            symbol_type=symbol_type,
            start_line=start,
            end_line=end,
            qualified_name=qualified,
            parent=parent_name,
            tree_parent=tree_parent,
            metadata=metadata,
        )
        self._add(symbol)

        child_class_base = class_base
        if symbol_type in _CONTAINER_TYPES and symbol_type not in {"enum", "type"}:
            base = self._class_route_base(node, all_decorators, class_base)
            if base:
                symbol.metadata["route_base"] = base
                child_class_base = base

        self._extract_routes(
            node,
            symbol,
            decorators=all_decorators,
            class_base=child_class_base,
        )

        if rule.recurse and (
            rule.container or symbol_type in {"function", "method"}
        ):
            self._visit_children(
                node,
                qualified,
                symbol_type,
                tree_parent=qualified,
                exported=exported,
                class_base=child_class_base,
            )

    def _symbol_metadata(
        self,
        node: Any,
        name: str,
        symbol_type: str,
        parent_name: str | None,
        *,
        exported: bool,
        decorators: list[Any] | None,
    ) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "language": self.language,
            "parent": parent_name,
            "signature": first_line(node),
            "exported": bool(
                exported or self._is_exported(node, name, symbol_type)
            ),
        }
        if decorators:
            metadata["decorators"] = [text_of(item).strip() for item in decorators]
        bases = self._bases(node)
        if bases:
            metadata["bases"] = bases
        if self.language == "python":
            doc = self._python_doc(node)
            if doc:
                metadata["doc"] = doc
        return metadata

    def _add(self, symbol: Symbol) -> None:
        key = (symbol.qualified_name, symbol.symbol_type, symbol.start_line)
        if key in self._seen:
            return
        self._seen.add(key)
        self.symbols.append(symbol)

    def _add_constant_node(
        self,
        *,
        node: Any,
        parent_name: str | None,
        tree_parent: str | None,
        start_line: int | None = None,
    ) -> None:
        name = child_text(node, "name")
        if name:
            self._add_constant(name, node, parent_name, tree_parent, start_line)

    def _add_constant(
        self,
        name: str,
        node: Any,
        parent_name: str | None,
        tree_parent: str | None,
        start_line: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        name = name.strip()
        if not name:
            return
        start, end = line_range(node)
        if start_line is not None:
            start = min(start, start_line)
        qualified = f"{parent_name}.{name}" if parent_name else name
        metadata = {
            "language": self.language,
            "parent": parent_name,
            "signature": first_line(node),
            "exported": self._is_exported(node, name, "constant"),
        }
        if extra:
            metadata.update(extra)
        self._add(
            Symbol(
                name=name,
                symbol_type="constant",
                start_line=start,
                end_line=end,
                qualified_name=qualified,
                parent=parent_name,
                tree_parent=tree_parent,
                metadata=metadata,
            )
        )

    # -- names and types ---------------------------------------------------

    def _name(self, node: Any, rule: SymbolRule) -> tuple[str | None, str | None]:
        language = self.language
        if language in {"c", "cpp"} and node.type == "function_definition":
            return _c_function_parts(node)
        if language in {"c", "cpp"} and node.type == "type_definition":
            declarator = node.child_by_field_name("declarator")
            return (text_of(declarator).strip() if declarator is not None else None, None)
        if language == "sql":
            return _sql_name(node), None

        if rule.name_field:
            value = child_text(node, rule.name_field)
            if value:
                return value, None
        for child in node.named_children:
            if child.type in rule.name_types:
                return text_of(child).strip(), None
        for type_name in (
            "identifier",
            "type_identifier",
            "simple_identifier",
            "constant",
            "field_identifier",
            "property_identifier",
            "name",
            "word",
            "function_name",
            "simple_name",
        ):
            for child in node.named_children:
                if child.type == type_name:
                    return text_of(child).strip(), None
        return None, None

    def _override_type(self, node: Any, symbol_type: str) -> str:
        if self.language == "go" and node.type in {"type_spec", "type_alias"}:
            if node.type == "type_alias":
                return "type"
            type_node = node.child_by_field_name("type")
            if type_node is not None:
                if type_node.type == "struct_type":
                    return "struct"
                if type_node.type == "interface_type":
                    return "interface"
            return "type"
        if self.language == "kotlin" and node.type == "class_declaration":
            text = text_of(node).lstrip()
            if re.match(r"(?:public\s+|private\s+|internal\s+|protected\s+|open\s+|data\s+|sealed\s+|abstract\s+)*interface\b", text):
                return "interface"
            if any(child.type == "enum_class_body" for child in node.named_children):
                return "enum"
            return "class"
        if self.language == "swift" and node.type == "class_declaration":
            kind = (child_text(node, "declaration_kind") or "class").lower()
            if kind in {"struct", "enum", "class", "extension", "actor"}:
                return kind
            return "class"
        return symbol_type

    def _bases(self, node: Any) -> list[str]:
        language = self.language
        values: list[str] = []
        for field in ("superclasses", "superclass", "base_list", "delegation_specifier"):
            value = child_text(node, field)
            if value:
                values.append(value)
        for child in node.named_children:
            if child.type in {
                "class_heritage",
                "base_class_clause",
                "base_clause",
                "inheritance_specifier",
                "superclass",
                "super_interfaces",
                "implements_clause",
                "class_interface_clause",
            }:
                values.append(text_of(child).strip())

        cleaned: list[str] = []
        for value in values:
            value = re.sub(r"^(extends|implements|:\s*)", "", value.strip())
            value = value.strip("() ")
            for part in re.split(r",(?![^<]*>)", value):
                item = part.strip().strip("() ")
                if item and item not in cleaned:
                    cleaned.append(item)
        return cleaned

    def _is_exported(self, node: Any, name: str, symbol_type: str) -> bool:
        language = self.language
        if language == "python":
            return not name.startswith("_")
        if language in {"javascript", "typescript"}:
            return text_of(node).lstrip().startswith("export")
        if language in {"java", "csharp", "kotlin", "swift", "php"}:
            text = text_of(node)
            return bool(re.search(r"\b(public|open)\b", text[:300]))
        if language == "go":
            return bool(name[:1].isupper())
        if language == "rust":
            return any(
                child.type == "visibility_modifier"
                and text_of(child).strip().startswith("pub")
                for child in node.named_children
            )
        return False

    def _python_doc(self, node: Any) -> str | None:
        body = node.child_by_field_name("body")
        if body is None:
            return None
        for child in body.named_children:
            if child.type == "expression_statement" and child.named_children:
                child = child.named_children[0]
            if child.type == "string":
                value = text_of(child).strip()
                return value.strip("\"'")[:500]
            break
        return None

    # -- language-specific constants --------------------------------------

    def _python_assignment(
        self, node: Any, parent_name: str | None, *, tree_parent: str | None
    ) -> None:
        left = node.child_by_field_name("left")
        if left is None or left.type != "identifier":
            return
        name = text_of(left).strip()
        if name.isupper():
            self._add_constant(name, node, parent_name, tree_parent)

    def _js_variables(
        self,
        node: Any,
        parent_name: str | None,
        *,
        tree_parent: str | None,
        start_line: int | None,
        exported: bool,
    ) -> None:
        kind = (child_text(node, "kind") or "var").lower()
        first = True
        for declarator in node.named_children:
            if declarator.type != "variable_declarator":
                continue
            name_node = declarator.child_by_field_name("name")
            if name_node is None or name_node.type != "identifier":
                continue
            name = text_of(name_node).strip()
            value = declarator.child_by_field_name("value")
            value_type = value.type if value is not None else ""

            if value_type in {
                "arrow_function",
                "function_expression",
                "function",
                "generator_function",
            }:
                start, end = line_range(declarator)
                if first and start_line is not None:
                    start = min(start, start_line)
                qualified = f"{parent_name}.{name}" if parent_name else name
                self._add(
                    Symbol(
                        name=name,
                        symbol_type="function",
                        start_line=start,
                        end_line=end,
                        qualified_name=qualified,
                        parent=parent_name,
                        tree_parent=tree_parent,
                        metadata={
                            "language": self.language,
                            "parent": parent_name,
                            "signature": first_line(declarator),
                            "exported": bool(exported),
                            "declaration_kind": kind,
                        },
                    )
                )
                first = False
                continue
            if value_type in {"class", "class_expression"}:
                start, end = line_range(declarator)
                if first and start_line is not None:
                    start = min(start, start_line)
                qualified = f"{parent_name}.{name}" if parent_name else name
                self._add(
                    Symbol(
                        name=name,
                        symbol_type="class",
                        start_line=start,
                        end_line=end,
                        qualified_name=qualified,
                        parent=parent_name,
                        tree_parent=tree_parent,
                        metadata={
                            "language": self.language,
                            "parent": parent_name,
                            "signature": first_line(declarator),
                            "exported": bool(exported),
                            "declaration_kind": kind,
                        },
                    )
                )
                first = False
                continue

            if value_type == "call_expression" and _is_require_call(value):
                continue
            if kind == "const" or name.isupper():
                self._add_constant(
                    name,
                    declarator,
                    parent_name,
                    tree_parent,
                    start_line if first else None,
                    extra={"declaration_kind": kind, "exported": bool(exported)},
                )
                first = False

    def _field_constants(
        self, node: Any, parent_name: str | None, *, tree_parent: str | None
    ) -> None:
        modifiers = text_of(
            next(
                (child for child in node.named_children if child.type == "modifiers"),
                node,
            )
        )
        for child in node.named_children:
            if child.type != "variable_declarator":
                continue
            name_node = child.child_by_field_name("name")
            if name_node is None:
                continue
            name = text_of(name_node).strip()
            if name.isupper():
                self._add_constant(
                    name,
                    child,
                    parent_name,
                    tree_parent,
                    extra={
                        "static": "static" in modifiers,
                        "readonly": "final" in modifiers,
                    },
                )

    def _csharp_field_constants(
        self, node: Any, parent_name: str | None, *, tree_parent: str | None
    ) -> None:
        text = text_of(node)
        is_const = bool(re.search(r"\bconst\b", text))
        found = False
        for child in _descendants(node, {"variable_declarator"}):
            name_node = child.child_by_field_name("name")
            if name_node is None:
                continue
            name = text_of(name_node).strip()
            if is_const or name.isupper():
                self._add_constant(name, child, parent_name, tree_parent)
                found = True
        if not found:
            for match in re.finditer(r"\b([A-Za-z_]\w*)\s*(?:=|;)", text):
                name = match.group(1)
                if is_const or name.isupper():
                    self._add_constant(name, node, parent_name, tree_parent)

    def _c_field_constants(
        self, node: Any, parent_name: str | None, *, tree_parent: str | None
    ) -> None:
        text = text_of(node)
        if not re.search(r"\b(const|constexpr)\b", text):
            return
        declarator = node.child_by_field_name("declarator")
        if declarator is None:
            return
        name, _ = _c_declarator_name(declarator)
        if name and (name.isupper() or "constexpr" in text):
            self._add_constant(name, node, parent_name, tree_parent)

    def _c_declaration_constants(
        self, node: Any, parent_name: str | None, *, tree_parent: str | None
    ) -> None:
        text = text_of(node).lstrip()
        if not re.match(r"(?:static\s+)?(?:const|constexpr)\b", text):
            return
        declarator = node.child_by_field_name("declarator")
        if declarator is None or declarator.type != "identifier":
            return
        name = text_of(declarator).strip()
        if name.isupper():
            self._add_constant(name, node, parent_name, tree_parent)

    def _go_type_spec(
        self, node: Any, parent_name: str | None, *, tree_parent: str | None
    ) -> None:
        name = child_text(node, "name")
        if not name:
            return
        symbol_type = self._override_type(node, "type")
        start, end = line_range(node)
        qualified = f"{parent_name}.{name}" if parent_name else name
        symbol = Symbol(
            name=name,
            symbol_type=symbol_type,
            start_line=start,
            end_line=end,
            qualified_name=qualified,
            parent=parent_name,
            tree_parent=tree_parent,
            metadata={
                "language": self.language,
                "parent": parent_name,
                "signature": first_line(node),
                "exported": name[:1].isupper(),
            },
        )
        self._add(symbol)
        if symbol_type in {"struct", "interface"}:
            self._visit_children(
                node,
                qualified,
                symbol_type,
                tree_parent=qualified,
            )

    def _c_type_definition(
        self, node: Any, parent_name: str | None, *, tree_parent: str | None
    ) -> None:
        declarator = node.child_by_field_name("declarator")
        type_node = node.child_by_field_name("type")
        name = text_of(declarator).strip() if declarator is not None else ""
        symbol_type = "type"
        if type_node is not None:
            symbol_type = {
                "struct_specifier": "struct",
                "union_specifier": "union",
                "enum_specifier": "enum",
            }.get(type_node.type, "type")
            if not name:
                name = child_text(type_node, "name") or ""
        if not name:
            return
        start, end = line_range(node)
        qualified = f"{parent_name}.{name}" if parent_name else name
        self._add(
            Symbol(
                name=name,
                symbol_type=symbol_type,
                start_line=start,
                end_line=end,
                qualified_name=qualified,
                parent=parent_name,
                tree_parent=tree_parent,
                metadata={
                    "language": self.language,
                    "parent": parent_name,
                    "signature": first_line(node),
                    "exported": False,
                    "typedef": True,
                },
            )
        )

    def _php_constants(
        self, node: Any, parent_name: str | None, *, tree_parent: str | None
    ) -> None:
        for child in node.named_children:
            if child.type != "const_element":
                continue
            name_node = next(
                (item for item in child.named_children if item.type == "name"),
                None,
            )
            if name_node is not None:
                self._add_constant(
                    text_of(name_node).strip(), child, parent_name, tree_parent
                )

    def _ruby_constant(
        self, node: Any, parent_name: str | None, *, tree_parent: str | None
    ) -> None:
        left = node.child_by_field_name("left")
        if left is not None and left.type == "constant":
            name = text_of(left).strip()
            if name.isupper():
                self._add_constant(name, node, parent_name, tree_parent)

    def _kotlin_property(
        self, node: Any, parent_name: str | None, *, tree_parent: str | None
    ) -> None:
        text = text_of(node).lstrip()
        name_node = next(
            (
                child
                for child in _descendants(node, {"simple_identifier"})
                if child.type == "simple_identifier"
            ),
            None,
        )
        if name_node is None:
            return
        name = text_of(name_node).strip()
        if text.startswith("const ") or name.isupper():
            self._add_constant(name, node, parent_name, tree_parent)

    def _swift_property(
        self, node: Any, parent_name: str | None, *, tree_parent: str | None
    ) -> None:
        binding = next(
            (
                child
                for child in node.named_children
                if child.type == "value_binding_pattern"
            ),
            None,
        )
        mutability = child_text(binding, "mutability") if binding is not None else None
        pattern = node.child_by_field_name("name")
        name_node = None
        if pattern is not None:
            name_node = next(
                (
                    child
                    for child in _descendants(pattern, {"simple_identifier"})
                ),
                None,
            )
        if name_node is None:
            name_node = next(
                (child for child in _descendants(node, {"simple_identifier"})),
                None,
            )
        if name_node is None:
            return
        name = text_of(name_node).strip()
        if mutability == "let" and (parent_name is None or name.isupper()):
            self._add_constant(name, node, parent_name, tree_parent)

    def _bash_constant(
        self, node: Any, parent_name: str | None, *, tree_parent: str | None
    ) -> None:
        name = child_text(node, "name")
        if name and name.isupper():
            self._add_constant(name, node, parent_name, tree_parent)

    def _powershell_constant(
        self, node: Any, parent_name: str | None, *, tree_parent: str | None
    ) -> None:
        text = text_of(node)
        match = re.match(r"\s*\$([A-Za-z_][\w]*)", text)
        if match and match.group(1).isupper():
            self._add_constant(match.group(1), node, parent_name, tree_parent)

    # -- routes ------------------------------------------------------------

    def _class_route_base(
        self, node: Any, decorators: list[Any], class_base: str | None
    ) -> str | None:
        if self.language in {"typescript", "javascript"}:
            for decorator in decorators:
                name, args = _decorator_name_args(text_of(decorator))
                if name in {"Controller", "Route"}:
                    path = _first_string(args or "")
                    if path:
                        return _join_paths(class_base, path)
        if self.language == "java":
            for annotation in _java_annotations(node):
                name = _annotation_name(annotation)
                if name in {"RequestMapping", "Path"}:
                    path = _first_string(text_of(annotation))
                    if path:
                        return _join_paths(class_base, path)
        if self.language == "csharp":
            for name, args, _ in _csharp_attributes(node):
                if name == "Route":
                    path = _first_string(args or "")
                    if path:
                        return _join_paths(class_base, path)
        return None

    def _extract_routes(
        self,
        node: Any,
        symbol: Symbol,
        *,
        decorators: list[Any],
        class_base: str | None,
    ) -> None:
        routes: list[str] = []
        if self.language == "python" and symbol.symbol_type in {"function", "method"}:
            for decorator in decorators:
                routes.extend(self._python_decorator_route(decorator, symbol))
        elif self.language in {"typescript", "javascript"} and symbol.symbol_type in {
            "function",
            "method",
        }:
            for decorator in decorators:
                label = self._nest_route(decorator, symbol, class_base)
                if label:
                    routes.append(label)
        elif self.language == "java" and symbol.symbol_type == "method":
            routes.extend(self._java_routes(node, symbol, class_base))
        elif self.language == "csharp" and symbol.symbol_type == "method":
            routes.extend(self._csharp_routes(node, symbol, class_base))
        if routes:
            symbol.metadata["routes"] = routes

    def _python_decorator_route(
        self, decorator: Any, symbol: Symbol
    ) -> list[str]:
        text = text_of(decorator).strip()
        target, args = _decorator_name_args(text)
        if not target:
            return []
        parts = target.split(".")
        prop = parts[-1]
        if prop not in _HTTP_METHODS and prop not in {"route", "api_route"}:
            return []
        path = _first_string(args or "")
        # ``@router.get("")`` is the common FastAPI form for a router's own
        # mount point: an empty path is a real route, but a decorator with no
        # string argument at all is not a route declaration.
        if not path and not re.search(r"[\"'`]", args or ""):
            return []
        methods: list[str] = []
        if prop in {"route", "api_route"}:
            methods = _methods_from_kwargs(args or "")
            framework = "flask" if prop == "route" else "fastapi"
        else:
            methods = [prop.upper()]
            framework = "fastapi"
        methods = methods or ["GET"]
        added: list[str] = []
        for method in methods:
            label = f"{method} {path}".strip()
            if self._add_route(
                label,
                decorator,
                symbol,
                method=method,
                path=path,
                framework=framework,
                handler_name=symbol.qualified_name,
            ):
                added.append(label)
        return added

    def _nest_route(
        self, decorator: Any, symbol: Symbol, class_base: str | None
    ) -> str | None:
        name, args = _decorator_name_args(text_of(decorator))
        if name not in _NEST_METHODS:
            return None
        method = _NEST_METHODS[name] or "GET"
        path = _join_paths(class_base, _first_string(args or "") or "")
        label = f"{method} {path}"
        self._add_route(
            label,
            decorator,
            symbol,
            method=method,
            path=path,
            framework="nestjs",
            handler_name=symbol.qualified_name,
        )
        return label

    def _java_routes(
        self, node: Any, symbol: Symbol, class_base: str | None
    ) -> list[str]:
        path = ""
        methods: list[str] = []
        route_node = None
        framework = "spring"
        for annotation in _java_annotations(node):
            name = _annotation_name(annotation)
            text = text_of(annotation)
            if name == "Path":
                path = _first_string(text) or path
                framework = "jax-rs"
                route_node = route_node or annotation
            elif name in _ANNOTATION_METHODS:
                mapped = _ANNOTATION_METHODS[name]
                if mapped:
                    methods.append(mapped)
                else:
                    found = re.findall(
                        r"RequestMethod\.([A-Z]+)", text
                    ) or re.findall(r"\b(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\b", text)
                    methods.extend(found or ["ANY"])
                path = _first_string(text) or path
                route_node = route_node or annotation
            elif name in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}:
                methods.append(name)
                framework = "jax-rs"
                route_node = route_node or annotation
        if not methods or route_node is None:
            return []
        full_path = _join_paths(class_base, path)
        labels: list[str] = []
        for method in dict.fromkeys(methods):
            label = f"{method} {full_path}"
            if self._add_route(
                label,
                route_node,
                symbol,
                method=method,
                path=full_path,
                framework=framework,
                handler_name=symbol.qualified_name,
            ):
                labels.append(label)
        return labels

    def _csharp_routes(
        self, node: Any, symbol: Symbol, class_base: str | None
    ) -> list[str]:
        path = ""
        methods: list[str] = []
        route_node = None
        for name, args, attribute in _csharp_attributes(node):
            if name == "Route":
                path = _first_string(args or "") or path
                route_node = route_node or attribute
            elif name in _CSHARP_METHODS:
                mapped = _CSHARP_METHODS[name]
                if mapped:
                    methods.append(mapped)
                else:
                    methods.append("ANY")
                path = _first_string(args or "") or path
                route_node = route_node or attribute
        if not methods or route_node is None:
            return []
        full_path = _join_paths(class_base, path)
        labels: list[str] = []
        for method in dict.fromkeys(methods):
            label = f"{method} {full_path}"
            if self._add_route(
                label,
                route_node,
                symbol,
                method=method,
                path=full_path,
                framework="aspnet",
                handler_name=symbol.qualified_name,
            ):
                labels.append(label)
        return labels

    def _add_route(
        self,
        label: str,
        node: Any,
        handler: Symbol,
        *,
        method: str,
        path: str,
        framework: str,
        handler_name: str,
    ) -> bool:
        key = (label, handler.qualified_name, handler_name)
        if key in self._route_seen:
            return False
        self._route_seen.add(key)
        start, end = line_range(node)
        self.symbols.append(
            Symbol(
                name=label[:255],
                symbol_type="route",
                start_line=start,
                end_line=end,
                qualified_name=f"{handler.qualified_name}#{label}"[:512],
                parent=handler.qualified_name,
                tree_parent=None,
                metadata={
                    "language": self.language,
                    "http_method": method,
                    "path": path,
                    "framework": framework,
                    "handler": handler_name,
                    "parent": handler.qualified_name,
                },
            )
        )
        return True

    def _extract_js_express_routes(self, root: Any) -> None:
        for node in _descendants(root, {"call_expression"}):
            function = node.child_by_field_name("function")
            if function is None or function.type != "member_expression":
                continue
            prop_node = function.child_by_field_name("property")
            object_node = function.child_by_field_name("object")
            if prop_node is None or object_node is None:
                continue
            prop = text_of(prop_node).strip().lower()
            if prop not in _HTTP_METHODS:
                continue
            object_text = text_of(object_node).strip()
            if not _routerish(object_text):
                continue
            arguments = node.child_by_field_name("arguments")
            path = _first_string(text_of(arguments)) if arguments is not None else ""
            if not path:
                path = _first_string(text_of(object_node))
            if not path:
                continue
            handler_name = ""
            if arguments is not None:
                parts = [
                    text_of(child).strip()
                    for child in arguments.named_children
                    if child.type not in {"string", "template_string"}
                ]
                handler_name = parts[0] if parts else ""
            label = f"{prop.upper()} {path}"
            start, end = line_range(node)
            key = (label, "", handler_name)
            if key in self._route_seen:
                continue
            self._route_seen.add(key)
            self.symbols.append(
                Symbol(
                    name=label[:255],
                    symbol_type="route",
                    start_line=start,
                    end_line=end,
                    qualified_name=f"route:{label}:{start}"[:512],
                    parent=None,
                    tree_parent=None,
                    metadata={
                        "language": self.language,
                        "http_method": prop.upper(),
                        "path": path,
                        "framework": "express",
                        "handler": handler_name,
                    },
                )
            )


# ---------------------------------------------------------------------------
# Helpers shared by the extractor


def _descendants(node: Any, types: set[str]):
    stack = list(node.named_children)
    while stack:
        child = stack.pop(0)
        if child.type in types:
            yield child
        stack = list(child.named_children) + stack


def _go_receiver_type(node: Any) -> str | None:
    receiver = node.child_by_field_name("receiver")
    if receiver is None:
        return None
    for type_node in _descendants(receiver, {"type_identifier"}):
        value = text_of(type_node).strip()
        if value:
            return value
    return None


def _c_function_parts(node: Any) -> tuple[str | None, str | None]:
    declarator = node.child_by_field_name("declarator")
    if declarator is None:
        return None, None
    function_declarator = next(
        _descendants(declarator, {"function_declarator"}), None
    )
    if function_declarator is None:
        return _c_declarator_name(declarator)
    inner = function_declarator.child_by_field_name("declarator")
    if inner is None:
        return None, None
    if inner.type == "qualified_identifier":
        full = text_of(inner).strip()
        if "::" in full:
            scope, name = full.rsplit("::", 1)
            return name, scope.replace("::", ".")
        return full, None
    return _c_declarator_name(inner)


def _c_declarator_name(node: Any) -> tuple[str | None, str | None]:
    current = node
    for _ in range(8):
        if current is None:
            return None, None
        if current.type in {
            "identifier",
            "field_identifier",
            "type_identifier",
            "operator_name",
            "destructor_name",
        }:
            return text_of(current).strip(), None
        if current.type == "qualified_identifier":
            full = text_of(current).strip()
            if "::" in full:
                scope, name = full.rsplit("::", 1)
                return name, scope.replace("::", ".")
            return full, None
        child = current.child_by_field_name("declarator")
        if child is None:
            candidate = next(
                (
                    item
                    for item in current.named_children
                    if item.type
                    in {
                        "identifier",
                        "field_identifier",
                        "type_identifier",
                        "qualified_identifier",
                        "operator_name",
                        "destructor_name",
                    }
                ),
                None,
            )
            if candidate is not None:
                return _c_declarator_name(candidate)
            return None, None
        current = child
    return None, None


def _sql_name(node: Any) -> str:
    if node.type == "create_index":
        for child in node.named_children:
            if child.type == "identifier":
                return text_of(child).strip()
    for reference in _descendants(node, {"object_reference"}):
        name = child_text(reference, "name")
        if name:
            return name
        return text_of(reference).strip()
    for child in node.named_children:
        if child.type == "identifier":
            return text_of(child).strip()
    return ""


def _is_require_call(node: Any) -> bool:
    function = node.child_by_field_name("function")
    if function is None:
        return False
    return function.type == "identifier" and text_of(function).strip() in {
        "require",
        "import",
    }


def _routerish(text: str) -> bool:
    lowered = text.lower()
    if "router" in lowered or "express(" in lowered:
        return True
    head = re.split(r"[.(\[]", lowered, maxsplit=1)[0]
    return head in {"app", "api", "server", "fastify", "route", "routes"}


def _first_string(text: str) -> str:
    match = re.search(r"[\"'`]([^\"'`]*)[\"'`]", text)
    return match.group(1) if match else ""


def _join_paths(base: str | None, path: str | None) -> str:
    base = (base or "").strip()
    path = (path or "").strip()
    if not base:
        return path or "/"
    if not path:
        return base
    if path == "/":
        return base
    return base.rstrip("/") + "/" + path.lstrip("/")


def _decorator_name_args(text: str) -> tuple[str | None, str | None]:
    match = re.match(r"\s*@\s*([\w.]+)\s*(?:\((.*)\))?", text, re.S)
    if not match:
        return None, None
    return match.group(1), match.group(2)


def _methods_from_kwargs(args: str) -> list[str]:
    match = re.search(r"methods\s*=\s*\[([^\]]*)\]", args, re.S)
    if match:
        return [item.upper() for item in re.findall(r"[\"'](\w+)[\"']", match.group(1))]
    match = re.search(r"methods\s*=\s*[\"'](\w+)[\"']", args)
    if match:
        return [match.group(1).upper()]
    return []


def _java_annotations(node: Any) -> list[Any]:
    found: list[Any] = []
    for child in node.named_children:
        if child.type == "modifiers":
            found.extend(
                item
                for item in child.named_children
                if item.type in {"annotation", "marker_annotation"}
            )
        elif child.type in {"annotation", "marker_annotation"}:
            found.append(child)
    return found


def _annotation_name(node: Any) -> str:
    value = child_text(node, "name") or ""
    return value.split(".")[-1]


def _csharp_attributes(node: Any) -> list[tuple[str, str | None, Any]]:
    found: list[tuple[str, str | None, Any]] = []
    for attribute_list in node.named_children:
        if attribute_list.type != "attribute_list":
            continue
        text = text_of(attribute_list).strip()
        if text.startswith("[") and text.endswith("]"):
            text = text[1:-1]
        for part in _split_top_level(text, ","):
            part = part.strip()
            if not part:
                continue
            match = re.match(
                r"([A-Za-z_][\w.]*)\s*(?:\((.*)\))?\s*$", part, re.S
            )
            if match:
                name = match.group(1).split(".")[-1]
                found.append((name, match.group(2), attribute_list))
    return found


def _split_top_level(text: str, separator: str) -> list[str]:
    """Split on a separator outside quotes and (), [] nesting."""
    parts: list[str] = []
    start = 0
    depth = 0
    quote: str | None = None
    for index, char in enumerate(text):
        if quote:
            if char == quote and (index == 0 or text[index - 1] != "\\"):
                quote = None
            continue
        if char in {"'", '"', "`"}:
            quote = char
        elif char in "([{":
            depth += 1
        elif char in ")]}":
            depth = max(depth - 1, 0)
        elif char == separator and depth == 0:
            parts.append(text[start:index])
            start = index + 1
    parts.append(text[start:])
    return parts


__all__ = ["Symbol", "SymbolRule", "extract_symbols"]
