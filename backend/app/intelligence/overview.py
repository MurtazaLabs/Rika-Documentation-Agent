"""§13.1 project overview: languages, layout, stack, entry points, hot modules.

Everything here is decidable from the index: file paths, detected languages,
stored import references and symbol counts. No model call, no second parse.
"""

from __future__ import annotations

import re
import sys

from app.intelligence.facts import FileFacts, ModuleResolver, ProjectFacts
from app.intelligence.layers import layer_for

_LANGUAGE_BY_EXTENSION = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".cs": "csharp",
    ".rb": "ruby",
    ".php": "php",
    ".kt": "kotlin",
    ".swift": "swift",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".sql": "sql",
    ".ps1": "powershell",
    ".sh": "shell",
    ".md": "markdown",
}

# Framework evidence: a package that is imported, or an asset that declares it.
_IMPORT_FRAMEWORKS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("FastAPI", ("fastapi",)),
    ("Starlette", ("starlette",)),
    ("SQLAlchemy", ("sqlalchemy",)),
    ("Alembic", ("alembic",)),
    ("Pydantic", ("pydantic", "pydantic_settings")),
    ("Celery", ("celery",)),
    ("pgvector", ("pgvector",)),
    ("Tree-sitter", ("tree_sitter",)),
    ("PostgreSQL driver", ("asyncpg", "psycopg")),
    ("Redis client", ("redis",)),
    ("PyMuPDF", ("fitz", "pymupdf")),
    ("python-docx", ("docx",)),
    ("openpyxl", ("openpyxl",)),
    ("pytest", ("pytest",)),
    ("Next.js", ("next",)),
    ("React", ("react",)),
    ("TanStack Query", ("@tanstack/react-query",)),
    ("Tailwind CSS", ("tailwindcss",)),
    ("Lucide icons", ("lucide-react",)),
)

_MANIFESTS = ("package.json", "requirements.txt", "pyproject.toml")

_ENTRY_BASENAMES: dict[str, str] = {
    "main.py": "Python module entry point",
    "app.py": "Python application module",
    "__main__.py": "Package entry point",
    "manage.py": "Management entry point",
    "wsgi.py": "WSGI entry point",
    "asgi.py": "ASGI entry point",
    "main.go": "Go program entry point",
    "program.cs": "ASP.NET entry point",
    "main.rs": "Rust binary entry point",
    "server.js": "Node server entry point",
    "server.ts": "Node server entry point",
    "index.js": "JavaScript module entry point",
    "index.ts": "TypeScript module entry point",
    "index.tsx": "React root component",
    "page.tsx": "Next.js route",
    "layout.tsx": "Next.js layout",
}

_CONFIG_KINDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("environment", (".env", ".env.example", ".env.local", ".env.sample")),
    ("container", ("dockerfile", "docker-compose.yml", "docker-compose.yaml", ".dockerignore")),
    ("python dependencies", ("requirements.txt", "requirements-dev.txt", "pyproject.toml",
                            "setup.py", "setup.cfg", "pipfile")),
    ("node", ("package.json", "tsconfig.json", "next.config.ts", "next.config.js",
              "postcss.config.mjs", "eslint.config.mjs", ".eslintrc.json")),
    ("database", ("alembic.ini",)),
    ("editor", (".editorconfig", ".gitignore", ".gitattributes")),
)

_CONFIG_EXTENSIONS = (".toml", ".ini", ".cfg", ".yaml", ".yml", ".conf", ".properties")
_MAX_LISTED_EVIDENCE = 6


def language_of(file: FileFacts) -> str | None:
    if file.language:
        return file.language
    name = file.name.lower()
    for extension, language in _LANGUAGE_BY_EXTENSION.items():
        if name.endswith(extension):
            return language
    return None


def overview(facts: ProjectFacts) -> dict:
    """Build the §13.1 report for one project."""
    resolver = ModuleResolver(facts.files)
    languages = _languages(facts)
    return {
        "project_id": facts.project_id,
        "name": facts.name,
        "description": facts.description,
        "totals": {
            "files": len(facts.files),
            "code_files": len(facts.code_files),
            "symbols": len(facts.symbols),
            "languages": len(languages),
        },
        "languages": languages,
        "directories": _directories(facts),
        "frameworks": _frameworks(facts),
        "entry_points": _entry_points(facts),
        "config_files": _config_files(facts),
        "important_modules": _important_modules(facts, resolver),
        "dependencies": _dependencies(facts, resolver),
    }


def _languages(facts: ProjectFacts) -> list[dict]:
    counts: dict[str, dict[str, int]] = {}
    for file in facts.files:
        language = language_of(file)
        if language is None:
            continue
        entry = counts.setdefault(language, {"files": 0, "symbols": 0, "bytes": 0})
        entry["files"] += 1
        entry["symbols"] += len(file.symbols)
        entry["bytes"] += file.size
    return [
        {"language": language, **values}
        for language, values in sorted(
            counts.items(), key=lambda item: (-item[1]["files"], item[0])
        )
    ]


def _directories(facts: ProjectFacts) -> list[dict]:
    counts: dict[str, dict[str, int]] = {}
    for file in facts.files:
        key = _directory_key(file.path)
        entry = counts.setdefault(key, {"files": 0, "symbols": 0, "bytes": 0})
        entry["files"] += 1
        entry["symbols"] += len(file.symbols)
        entry["bytes"] += file.size
    return [
        {"path": path or "(root)", **values}
        for path, values in sorted(
            counts.items(), key=lambda item: (-item[1]["files"], item[0])
        )[:15]
    ]


def _directory_key(path: str) -> str:
    parts = path.split("/")[:-1]
    if not parts:
        return ""
    if parts[0] in {"backend", "frontend", "src", "app", "packages"} and len(parts) > 1:
        return "/".join(parts[:2])
    return parts[0]


def _frameworks(facts: ProjectFacts) -> list[dict]:
    evidence: dict[str, list[str]] = {}
    for file in facts.files:
        haystacks = [item.reference.lower() for item in file.imports]
        is_manifest = file.name.lower() in _MANIFESTS
        if is_manifest:
            haystacks.append(file.text.lower()[:MAX_MANIFEST_CHARS])
        for framework, markers in _IMPORT_FRAMEWORKS:
            for haystack in haystacks:
                if any(_mentions(haystack, marker) for marker in markers):
                    paths = evidence.setdefault(framework, [])
                    if file.path not in paths:
                        paths.append(file.path)
                    break
    found = [
        {"name": name, "evidence": paths[:_MAX_LISTED_EVIDENCE], "files": len(paths)}
        for name, paths in evidence.items()
    ]
    return sorted(found, key=lambda item: (-item["files"], item["name"]))


MAX_MANIFEST_CHARS = 20_000


def _mentions(haystack: str, marker: str) -> bool:
    if marker.startswith("@"):
        return marker in haystack
    return re.search(rf"(?<![\w.-]){re.escape(marker)}(?![\w-])", haystack) is not None


def _entry_points(facts: ProjectFacts) -> list[dict]:
    found: list[dict] = []
    for file in facts.files:
        lowered = file.name.lower()
        kind = _ENTRY_BASENAMES.get(lowered)
        if kind is None:
            continue
        detail = None
        if lowered == "main.py" and "FastAPI(" in file.text:
            detail = "FastAPI application factory"
        elif lowered == "main.py" and 'if __name__ == "__main__"' in file.text:
            detail = "script entry point"
        elif lowered in {"page.tsx", "layout.tsx"}:
            detail = f"Next.js {lowered.split('.')[0]} route"
        found.append({"path": file.path, "kind": kind, "detail": detail})

    for file in facts.files:
        if file.path.startswith("scripts/") and file.name.lower().endswith(".ps1"):
            found.append(
                {"path": file.path, "kind": "Operational script", "detail": "PowerShell helper"}
            )
    return sorted(found, key=lambda item: (item["kind"], item["path"]))[:20]


def _config_files(facts: ProjectFacts) -> list[dict]:
    found: list[dict] = []
    for file in facts.files:
        named = file.name.lower()
        kind = next(
            (label for label, names in _CONFIG_KINDS if named in names),
            None,
        )
        if kind is None and named.endswith(_CONFIG_EXTENSIONS):
            kind = "configuration"
        if kind is None:
            continue
        found.append({"path": file.path, "kind": kind})
    return sorted(found, key=lambda item: (item["kind"], item["path"]))


def _important_modules(facts: ProjectFacts, resolver: ModuleResolver) -> list[dict]:
    imported_by: dict[str, int] = {}
    for file in facts.files:
        targets = {
            resolved
            for item in file.imports
            if (resolved := resolver.resolve(file, item.reference)) and resolved != file.path
        }
        for target in targets:
            imported_by[target] = imported_by.get(target, 0) + 1

    scored: list[dict] = []
    for file in facts.code_files:
        if not file.symbols:
            continue
        dependents = imported_by.get(file.path, 0)
        score = dependents * 3 + len(file.symbols)
        scored.append(
            {
                "path": file.path,
                "layer": layer_for(file.path)[0],
                "symbols": len(file.symbols),
                "imported_by": dependents,
                "score": score,
            }
        )
    return sorted(scored, key=lambda item: (-item["score"], item["path"]))[:10]


def _dependencies(facts: ProjectFacts, resolver: ModuleResolver) -> dict:
    roots = {
        file.path.split("/", 1)[0] for file in facts.code_files if "/" in file.path
    }
    internal = 0
    unresolved = 0
    packages: dict[str, set[str]] = {}
    for file in facts.files:
        for item in file.imports:
            target = resolver.resolve(file, item.reference)
            if target is not None:
                internal += 1
                continue
            package = _package_name(item.reference)
            if package is None or package in sys.stdlib_module_names:
                continue
            # An import that names the project's own package but matched no
            # indexed file points at code outside the index, not at a dependency.
            if package in roots or package in {"app", "src"}:
                unresolved += 1
                continue
            packages.setdefault(package, set()).add(file.path)

    return {
        "internal_edges": internal,
        "unresolved_edges": unresolved,
        "external_edges": sum(len(paths) for paths in packages.values()),
        "packages": [
            {"name": name, "files": len(paths)}
            for name, paths in sorted(
                packages.items(), key=lambda item: (-len(item[1]), item[0])
            )[:15]
        ],
    }


def _package_name(reference: str) -> str | None:
    text = reference.strip().strip("'\";").replace("\\", "/")
    if not text or text.startswith((".", "/", "@/")):
        return None
    if text.startswith("@"):
        parts = text.split("/")
        return "/".join(parts[:2]) if len(parts) >= 2 else parts[0]
    head = text.replace("/", ".").split(".")[0]
    return head or None
