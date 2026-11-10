"""Code intelligence: symbols, parents, routes, imports and code chunking."""

from __future__ import annotations

from app.code_intelligence import CodeAnalysis, Symbol, analyze_code
from app.code_intelligence.chunking import chunk_code


def by_qualified_name(analysis: CodeAnalysis) -> dict[str, Symbol]:
    return {symbol.qualified_name: symbol for symbol in analysis.symbols}


def dependency_targets(analysis: CodeAnalysis) -> list[tuple[str, str]]:
    return [
        (dependency.target_reference, dependency.dependency_type)
        for dependency in analysis.dependencies
    ]


PYTHON_SOURCE = '''import os
from .pkg import thing

API_KEY = "secret"
MAX_SIZE = 10

@router.get("/items")
async def list_items():
    return []

class Service(Base):
    """Service doc."""

    CONSTANT = 1

    def run(self):
        return list_items()
'''


def test_python_symbols_routes_parents_and_imports() -> None:
    analysis = analyze_code("python", PYTHON_SOURCE, "app/service.py")

    assert analysis.grammar == "python"
    assert analysis.warnings == []
    symbols = by_qualified_name(analysis)

    assert symbols["API_KEY"].symbol_type == "constant"
    assert symbols["MAX_SIZE"].symbol_type == "constant"

    items = symbols["list_items"]
    assert items.symbol_type == "function"
    assert (items.start_line, items.end_line) == (7, 9)
    assert items.metadata["routes"] == ["GET /items"]

    service = symbols["Service"]
    assert service.symbol_type == "class"
    assert service.metadata["bases"] == ["Base"]
    assert service.metadata["doc"] == "Service doc."
    assert (service.start_line, service.end_line) == (11, 17)

    run = symbols["Service.run"]
    assert run.symbol_type == "method"
    assert run.parent == "Service"
    assert run.tree_parent == "Service"
    assert symbols["Service.CONSTANT"].parent == "Service"

    route = symbols["list_items#GET /items"]
    assert route.symbol_type == "route"
    assert route.metadata["http_method"] == "GET"
    assert route.metadata["path"] == "/items"
    assert route.metadata["framework"] == "fastapi"
    assert route.metadata["handler"] == "list_items"

    assert dependency_targets(analysis) == [
        ("os", "import"),
        (".pkg", "import"),
    ]


def test_flask_route_lists_every_declared_method() -> None:
    source = '''from flask import Flask
app = Flask(__name__)

@app.route("/items", methods=["GET", "POST"])
def items():
    return "ok"
'''
    analysis = analyze_code("python", source, "app.py")

    symbols = by_qualified_name(analysis)
    assert symbols["items"].metadata["routes"] == ["GET /items", "POST /items"]
    assert symbols["items#GET /items"].metadata["framework"] == "flask"
    assert symbols["items#POST /items"].metadata["framework"] == "flask"
    assert dependency_targets(analysis) == [("flask", "import")]


def test_javascript_express_routes_and_imports() -> None:
    source = '''import { helper } from "./helper.js";

export function load() { return helper(); }

const BIG_LIMIT = 10;

router.post("/items", createItem);
'''
    analysis = analyze_code("javascript", source, "src/routes.js")

    symbols = by_qualified_name(analysis)
    assert symbols["load"].symbol_type == "function"
    assert symbols["BIG_LIMIT"].symbol_type == "constant"

    route = symbols["route:POST /items:7"]
    assert route.symbol_type == "route"
    assert route.metadata["framework"] == "express"
    assert route.metadata["path"] == "/items"
    assert route.metadata["handler"] == "createItem"

    assert dependency_targets(analysis) == [("./helper.js", "import")]


def test_typescript_interfaces_types_and_nest_routes() -> None:
    source = '''import { A } from "./a";

export interface User { id: string }

export type Mode = "on" | "off";

@Controller("users")
export class UsersController {
  @Get(":id")
  find(@Param("id") id: string) { return id; }
}
'''
    analysis = analyze_code("typescript", source, "src/users.ts")

    symbols = by_qualified_name(analysis)
    assert symbols["User"].symbol_type == "interface"
    assert symbols["Mode"].symbol_type == "type"
    assert symbols["UsersController"].symbol_type == "class"

    find = symbols["UsersController.find"]
    assert find.symbol_type == "method"
    assert find.parent == "UsersController"
    assert find.tree_parent == "UsersController"
    assert find.metadata["routes"] == ["GET users/:id"]

    route = symbols["UsersController.find#GET users/:id"]
    assert route.metadata["framework"] == "nestjs"
    assert route.metadata["path"] == "users/:id"
    assert dependency_targets(analysis) == [("./a", "import")]


def test_java_spring_routes_include_the_class_prefix() -> None:
    source = '''package demo;
import java.util.List;
@RestController
@RequestMapping("/api")
public class DemoController {
    private static final int MAX = 10;
    @GetMapping("/items/{id}")
    public String item(String id) { return id; }
}
'''
    analysis = analyze_code("java", source, "DemoController.java")

    symbols = by_qualified_name(analysis)
    controller = symbols["DemoController"]
    assert controller.symbol_type == "class"
    assert controller.metadata["route_base"] == "/api"
    assert (controller.start_line, controller.end_line) == (3, 9)

    assert symbols["DemoController.MAX"].symbol_type == "constant"
    method = symbols["DemoController.item"]
    assert method.symbol_type == "method"
    assert method.parent == "DemoController"
    assert method.metadata["routes"] == ["GET /api/items/{id}"]

    route = symbols["DemoController.item#GET /api/items/{id}"]
    assert route.parent == "DemoController.item"
    assert route.metadata["framework"] == "spring"
    assert dependency_targets(analysis) == [("java.util.List", "import")]


def test_csharp_attributes_and_const_fields() -> None:
    source = '''using System;
namespace Demo {
    [Route("api/[controller]")]
    public class ItemsController {
        public const int Max = 10;
        [HttpGet("{id}")]
        public string Get(int id) => "x";
    }
}
'''
    analysis = analyze_code("csharp", source, "ItemsController.cs")

    symbols = by_qualified_name(analysis)
    assert symbols["Demo"].symbol_type == "namespace"
    controller = symbols["Demo.ItemsController"]
    assert controller.symbol_type == "class"
    assert controller.metadata["route_base"] == "api/[controller]"

    constant = symbols["Demo.ItemsController.Max"]
    assert constant.symbol_type == "constant"
    assert constant.metadata["parent"] == "Demo.ItemsController"

    method = symbols["Demo.ItemsController.Get"]
    assert method.metadata["routes"] == ["GET api/[controller]/{id}"]
    route = symbols["Demo.ItemsController.Get#GET api/[controller]/{id}"]
    assert route.metadata["framework"] == "aspnet"
    assert dependency_targets(analysis) == [("System", "using")]


def test_go_receiver_is_the_logical_parent_but_not_the_tree_parent() -> None:
    source = '''package demo
import (
    "fmt"
    alias "net/http"
)
const Max = 10
type Service struct { Name string }
func (s *Service) Run() { fmt.Println() }
func Hello() {}
'''
    analysis = analyze_code("go", source, "service.go")

    symbols = by_qualified_name(analysis)
    assert symbols["Service"].symbol_type == "struct"
    assert symbols["Max"].symbol_type == "constant"

    run = symbols["Service.Run"]
    assert run.symbol_type == "method"
    assert run.parent == "Service"
    assert run.tree_parent is None
    assert symbols["Hello"].symbol_type == "function"

    assert dependency_targets(analysis) == [
        ("fmt", "import"),
        ("net/http", "import"),
    ]


def test_rust_impl_methods_are_logical_children_but_top_level_chunks() -> None:
    source = '''use std::fmt;

pub struct Service { name: String }

trait Runnable { fn run(&self); }

impl Runnable for Service {
    fn run(&self) {}
}

impl Service {
    pub fn new() -> Self { Service { name: String::new() } }
}

fn helper() {}
'''
    analysis = analyze_code("rust", source, "service.rs")

    symbols = by_qualified_name(analysis)
    assert symbols["Service"].symbol_type == "struct"
    assert symbols["Runnable"].symbol_type == "trait"
    assert symbols["Runnable.run"].parent == "Runnable"
    assert symbols["Runnable.run"].tree_parent == "Runnable"

    run = symbols["Service.run"]
    assert run.parent == "Service"
    assert run.tree_parent is None
    assert symbols["Service.new"].parent == "Service"
    assert symbols["helper"].symbol_type == "function"
    assert dependency_targets(analysis) == [("std::fmt", "import")]


def test_grammar_resolution_uses_the_file_extension() -> None:
    analysis = analyze_code(
        "typescript", "export const App = () => <div />;\n", "App.tsx"
    )

    assert analysis.grammar == "tsx"
    assert analysis.warnings == []


def test_embedded_component_scripts_produce_symbols() -> None:
    source = '''<script>
  import { onMount } from 'svelte';
  let count = 0;
  function increment() { count += 1; }
</script>
<h1>{count}</h1>
'''
    analysis = analyze_code("svelte", source, "Counter.svelte")

    increment = by_qualified_name(analysis)["increment"]
    assert increment.start_line == 4
    assert increment.end_line == 4
    assert increment.metadata["embedded_script"] is True
    assert dependency_targets(analysis) == [("svelte", "import")]

    drafts = chunk_code(source, analysis, max_chars=80, overlap_chars=10)
    named = [draft for draft in drafts if draft.symbol_name == "increment"]
    assert named
    assert named[0].start_line == 4


def test_unknown_language_degrades_to_a_warning() -> None:
    analysis = analyze_code("brainfuck", "+++[>+<-]", "program.bf")

    assert analysis.failed is True
    assert analysis.grammar is None
    assert analysis.symbols == []
    assert analysis.dependencies == []
    assert analysis.warnings


def test_chunk_code_keeps_a_small_file_whole() -> None:
    source = "def add(a, b):\n    return a + b\n"
    analysis = analyze_code("python", source, "add.py")

    drafts = chunk_code(source, analysis, max_chars=400, overlap_chars=50)

    assert len(drafts) == 1
    draft = drafts[0]
    assert draft.start_line == 1
    assert draft.end_line >= 2
    assert draft.symbol_name == "add"
    assert draft.metadata["symbols"] == ["add"]
    assert draft.metadata["grammar"] == "python"


def test_chunk_code_splits_an_oversized_function() -> None:
    lines = ["import os", "", "def huge(values):", "    total = 0"]
    for index in range(20):
        lines.append(f"    total += values[{index}]  # a somewhat long comment")
    lines.append("    return total")
    source = "\n".join(lines)
    analysis = analyze_code("python", source, "huge.py")

    drafts = chunk_code(source, analysis, max_chars=150, overlap_chars=20)

    parts = [draft for draft in drafts if draft.symbol_name == "huge"]
    assert len(parts) > 1
    assert all(draft.metadata["symbol_part"] == "part" for draft in parts)
    assert all(draft.metadata["symbol_type"] == "function" for draft in parts)
    assert parts[0].start_line == 3
    assert parts[-1].end_line == len(lines)
    for draft in drafts:
        assert 1 <= draft.start_line <= draft.end_line <= len(lines)


def test_chunk_code_splits_an_oversized_class_into_container_parts() -> None:
    source = '''class Service:
    """A service."""

    def first(self):
        return 1

    def second(self):
        return 2

    def third(self):
        return 3

    trailing = 4
'''
    analysis = analyze_code("python", source, "service.py")

    drafts = chunk_code(source, analysis, max_chars=80, overlap_chars=10)

    header = next(d for d in drafts if d.metadata.get("symbol_part") == "header")
    assert header.symbol_name == "Service"
    assert header.start_line == 1
    assert "class Service:" in header.text

    children = [
        draft
        for draft in drafts
        if draft.symbol_name in {"first", "second", "third"}
    ]
    assert [draft.symbol_name for draft in children] == ["first", "second", "third"]
    assert all(draft.metadata["symbol_type"] == "method" for draft in children)
    assert all(draft.metadata["parent_symbol"] == "Service" for draft in children)
    assert [draft.start_line for draft in children] == [4, 7, 10]

    tail = next(d for d in drafts if d.metadata.get("symbol_part") == "tail")
    assert tail.symbol_name == "Service"
    assert tail.text.strip() == "trailing = 4"


def test_chunk_code_without_symbols_falls_back_to_line_chunks() -> None:
    source = "\n".join(f"print({index})" for index in range(30))
    analysis = analyze_code("python", source, "script.py")
    assert analysis.symbols == []

    drafts = chunk_code(source, analysis, max_chars=60, overlap_chars=0)

    assert len(drafts) > 1
    assert all(draft.symbol_name is None for draft in drafts)
    assert drafts[0].start_line == 1
    assert drafts[-1].end_line == 30
    for draft in drafts:
        assert 1 <= draft.start_line <= draft.end_line <= 30
