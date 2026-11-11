"""§13.5 bug investigation: defects the index can prove, and suspicions it cannot.

Each finding carries ``confidence``: ``confirmed`` means the evidence is complete
within the index (a route that exists but is undocumented, an import that names a
module the project does not contain); ``possible`` means a human still has to
look, because the index cannot see runtime behaviour or files outside the project.
"""

from __future__ import annotations

import hashlib
import re

from app.config import Settings
from app.intelligence.facts import ModuleResolver, ProjectFacts

_PYTHON_BUILTINS = {
    "Exception", "ValueError", "TypeError", "KeyError", "RuntimeError", "BaseException",
    "AssertionError", "StopIteration", "OSError", "IOError", "IndexError", "AttributeError",
    "NotImplementedError", "LookupError", "TimeoutError", "FileNotFoundError",
    "PermissionError", "ConnectionError", "UnicodeDecodeError", "ZeroDivisionError",
    "Path", "UUID", "StrEnum", "Enum", "Any", "Optional", "Callable", "Iterable",
    "Sequence", "Mapping", "Literal", "TypeVar", "Generic", "Protocol", "Decimal",
    "Dataclass", "List", "Dict", "Set", "Tuple", "Type", "ClassVar", "Final",
}
_CALL = re.compile(r"\b([A-Z][A-Za-z0-9_]*)\s*\(")
_BARE_EXCEPT = re.compile(r"^\s*except\s*:", re.MULTILINE)
_SWALLOWED = re.compile(r"^\s*except[^:\n]*:\s*\n\s*pass\b", re.MULTILINE)
_MARKER = re.compile(r"\b(TODO|FIXME|XXX|HACK)\b")
_GETENV = re.compile(r"os\.(?:getenv|environ\.get)\(\s*[\"']([A-Z][A-Z0-9_]{2,})[\"']")
_FROM_IMPORT = re.compile(r"^\s*from\s+[\w.]+\s+import\s+\(?([^)\n]+)", re.MULTILINE)
_MAX_DUPLICATE_BODY = 4000
_MIN_DUPLICATE_LINES = 4


def investigate(facts: ProjectFacts) -> dict:
    resolver = ModuleResolver(facts.files)
    findings: list[dict] = []
    findings.extend(_broken_imports(facts, resolver))
    findings.extend(_undefined_references(facts))
    findings.extend(_duplicates(facts))
    findings.extend(_risky_patterns(facts))
    findings.extend(_config_mismatches(facts))

    confirmed = sum(1 for finding in findings if finding["confidence"] == "confirmed")
    by_kind: dict[str, int] = {}
    for finding in findings:
        by_kind[finding["kind"]] = by_kind.get(finding["kind"], 0) + 1
    return {
        "project_id": facts.project_id,
        "summary": {
            "confirmed": confirmed,
            "possible": len(findings) - confirmed,
            "by_kind": by_kind,
        },
        "findings": sorted(
            findings,
            key=lambda item: (item["confidence"] != "confirmed", item["kind"], item["message"]),
        ),
    }


def _broken_imports(facts: ProjectFacts, resolver: ModuleResolver) -> list[dict]:
    findings: list[dict] = []
    root_packages = {
        file.path.split("/", 1)[0] for file in facts.code_files if "/" in file.path
    }
    for file in facts.code_files:
        for item in file.imports:
            if resolver.resolve(file, item.reference) is not None:
                continue
            reference = item.reference.strip()
            head = reference.replace("/", ".").split(".")[0]
            if resolver.looks_internal(reference):
                confidence, reason = (
                    "possible",
                    "relative or aliased import; the alias mapping is not indexed",
                )
            elif head in root_packages:
                confidence, reason = (
                    "confirmed",
                    f"names the project package {head!r}, but no indexed file matches",
                )
            else:
                continue
            findings.append(
                _finding(
                    "broken_import",
                    confidence,
                    "error" if confidence == "confirmed" else "warning",
                    f"{file.path} imports {reference}, which does not resolve",
                    {
                        "file_path": file.path,
                        "reference": reference,
                        "dependency_type": item.dependency_type,
                        "reason": reason,
                    },
                )
            )
    return findings


def _undefined_references(facts: ProjectFacts) -> list[dict]:
    """Classes used by a Python file but defined in another file and never imported."""
    definitions: dict[str, list[str]] = {}
    for file in facts.code_files:
        for symbol in file.symbols:
            if symbol.symbol_type in {"class", "struct", "interface", "type"}:
                definitions.setdefault(symbol.name, []).append(file.path)

    findings: list[dict] = []
    for file in facts.code_files:
        if file.language != "python" or "(" not in file.text:
            continue
        local = {symbol.name for symbol in file.symbols}
        imported = _imported_names(file.text)
        if "*" in imported:  # ``import *`` hides where each name comes from
            continue
        seen: set[str] = set()
        for match in _CALL.finditer(file.text):
            name = match.group(1)
            if (
                name in seen
                or name in local
                or name in imported
                or name in _PYTHON_BUILTINS
                or name not in definitions
            ):
                continue
            elsewhere = [path for path in definitions[name] if path != file.path]
            if not elsewhere:
                continue
            seen.add(name)
            findings.append(
                _finding(
                    "possible_missing_import",
                    "possible",
                    "warning",
                    f"{file.path} uses {name} without importing it",
                    {
                        "file_path": file.path,
                        "name": name,
                        "line": file.text.count("\n", 0, match.start()) + 1,
                        "defined_in": elsewhere[:3],
                    },
                )
            )
    return findings


def _duplicates(facts: ProjectFacts) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for file in facts.code_files:
        for symbol in file.symbols:
            if symbol.symbol_type not in {"function", "method"}:
                continue
            body = file.slice_lines(symbol.start_line + 1, symbol.end_line)
            if len(body) > _MAX_DUPLICATE_BODY:
                continue
            normalised = _normalise_body(body)
            if normalised.count("\n") < _MIN_DUPLICATE_LINES or len(normalised) < 120:
                continue
            digest = hashlib.sha1(normalised.encode()).hexdigest()
            groups.setdefault(digest, []).append(
                {"path": file.path, "name": symbol.name,
                 "qualified_name": symbol.qualified_name, "line": symbol.start_line}
            )

    findings: list[dict] = []
    for copies in groups.values():
        if len(copies) < 2:
            continue
        locations = "; ".join(f"{copy['path']}:{copy['line']}" for copy in copies)
        findings.append(
            _finding(
                "duplicate_implementation",
                "possible",
                "info",
                f"{len(copies)} copies of the same implementation: {locations}",
                {"symbols": copies},
            )
        )
    return findings


def _risky_patterns(facts: ProjectFacts) -> list[dict]:
    findings: list[dict] = []
    for file in facts.code_files:
        for number, line in enumerate(file.lines, start=1):
            if _BARE_EXCEPT.match(line):
                findings.append(
                    _finding(
                        "bare_except",
                        "confirmed",
                        "warning",
                        f"{file.path}:{number} catches every exception, including "
                        "KeyboardInterrupt and SystemExit",
                        {"file_path": file.path, "line": number},
                    )
                )
            marker = _MARKER.search(line)
            if marker:
                findings.append(
                    _finding(
                        "unresolved_marker",
                        "possible",
                        "info",
                        f"{file.path}:{number} carries a {marker.group(1)} marker",
                        {"file_path": file.path, "line": number,
                         "text": line.strip()[:200]},
                    )
                )
    for file in facts.code_files:
        for match in _SWALLOWED.finditer(file.text):
            line = file.text.count("\n", 0, match.start()) + 1
            findings.append(
                _finding(
                    "swallowed_exception",
                    "possible",
                    "warning",
                    f"{file.path}:{line} catches an exception and silently ignores it",
                    {"file_path": file.path, "line": line},
                )
            )
    return findings


def _config_mismatches(facts: ProjectFacts) -> list[dict]:
    findings: list[dict] = []
    settings = Settings.model_fields
    example_keys: set[str] = set()
    for file in facts.files:
        if file.name.lower() not in {".env.example", ".env.sample", ".env.template"}:
            continue
        for number, line in enumerate(file.lines, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            key = key.strip()
            example_keys.add(key)
            field = settings.get(key.lower())
            if field is None or value.strip() in {"", "VERIFY_BEFORE_USE"}:
                continue
            default = field.default
            if default is None or isinstance(default, (list, dict)):
                continue
            if str(default).lower() != value.strip().lower():
                findings.append(
                    _finding(
                        "config_default_mismatch",
                        "possible",
                        "warning",
                        f"{file.path}:{number} sets {key}={value.strip()}, but the "
                        f"default is {default}",
                        {"file_path": file.path, "line": number, "key": key,
                         "documented": value.strip(), "default": str(default)},
                    )
                )

    for file in facts.code_files:
        if file.language != "python":
            continue
        for number, line in enumerate(file.lines, start=1):
            for match in _GETENV.finditer(line):
                key = match.group(1)
                if key in example_keys or key.lower() in settings:
                    continue
                findings.append(
                    _finding(
                        "undocumented_environment_variable",
                        "possible",
                        "info",
                        f"{file.path}:{number} reads {key}, which no example file declares",
                        {"file_path": file.path, "line": number, "variable": key},
                    )
                )
    return findings


def _imported_names(text: str) -> set[str]:
    """Every identifier a Python file's import statements bring into scope.

    Read from the source rather than the dependency edges: edges store module
    paths, so ``from app.models import Document`` would otherwise look like a
    missing import for ``Document``.
    """
    names: set[str] = set()
    for match in _FROM_IMPORT.finditer(text):
        for part in match.group(1).split("#", 1)[0].split(","):
            pieces = part.strip().strip("()").split(" as ")
            candidate = pieces[-1].strip()
            if candidate.startswith("*"):
                return {"*"}
            if candidate.isidentifier():
                names.add(candidate)
    return names


def _normalise_body(body: str) -> str:
    lines = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith(('"""', "'''")):
            continue
        lines.append(stripped)
    return "\n".join(lines)


def _finding(
    kind: str,
    confidence: str,
    severity: str,
    message: str,
    details: dict,
) -> dict:
    return {
        "kind": kind,
        "confidence": confidence,
        "severity": severity,
        "message": message,
        "details": details,
    }
