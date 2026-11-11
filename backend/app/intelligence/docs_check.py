"""§13.4 documentation comparison: what the docs claim versus what is built.

Four comparisons, each with the evidence kept so the UI can show both sides:
README route tables vs discovered routes, documented tables vs ORM tables,
environment variables vs settings fields, and markdown links vs indexed files.
"""

from __future__ import annotations

import re

from app.config import Settings
from app.intelligence.architecture import request_flows, tables
from app.intelligence.facts import FileFacts, ModuleResolver, ProjectFacts

_INLINE_ROUTE = re.compile(
    r"`?(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+(/[^`\s|]*)`?"
)
_ENV_KEY = re.compile(r"^\s*([A-Z][A-Z0-9_]{2,})\s*=", re.MULTILINE)
_MD_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def compare(facts: ProjectFacts) -> dict:
    readme = _readme(facts)
    findings: list[dict] = []

    documented = _documented_routes(readme) if readme else []
    implemented = _implemented_routes(facts)
    findings.extend(_route_findings(documented, implemented))

    if readme is not None:
        findings.extend(_table_findings(facts, readme))
    findings.extend(_setting_findings(facts))
    findings.extend(_link_findings(facts))

    return {
        "project_id": facts.project_id,
        "readme": readme.path if readme else None,
        "routes": {
            "documented": len(documented),
            "implemented": len(implemented),
        },
        "findings": findings,
    }


def _readme(facts: ProjectFacts) -> FileFacts | None:
    return next(
        (file for file in facts.files if file.name.lower().startswith("readme")),
        None,
    )


def _documented_routes(readme: FileFacts) -> list[dict]:
    routes: dict[tuple[str, str], int] = {}
    for number, line in enumerate(readme.lines, start=1):
        if "|" in line:
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if len(cells) >= 2:
                method_cell = cells[0].strip("` ").upper()
                path_cell = cells[1].strip("` ")
                if method_cell in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}:
                    if path_cell.startswith("/"):
                        routes[(method_cell, _normalise_path(path_cell))] = number
                        continue
        for match in _INLINE_ROUTE.finditer(line):
            routes[(match.group(1), _normalise_path(match.group(2)))] = number
    return [
        {"method": method, "path": path, "line": line}
        for (method, path), line in routes.items()
    ]


def _implemented_routes(facts: ProjectFacts) -> list[dict]:
    seen: dict[tuple[str, str], dict] = {}
    for flow in request_flows(facts, ModuleResolver(facts.files)):
        key = (flow["method"], _normalise_path(flow["path"]))
        seen.setdefault(
            key,
            {
                "method": flow["method"],
                "path": key[1],
                "file_path": flow["file_path"],
                "line": flow["line"],
                "handler": flow["handler"],
            },
        )
    return list(seen.values())


def _route_findings(documented: list[dict], implemented: list[dict]) -> list[dict]:
    documented_keys = {(item["method"], item["path"]) for item in documented}
    implemented_keys = {(item["method"], item["path"]) for item in implemented}
    findings: list[dict] = []

    for item in implemented:
        key = (item["method"], item["path"])
        if key not in documented_keys:
            findings.append(
                _finding(
                    "route_missing_in_docs",
                    "warning",
                    confirmed=True,
                    message=f"{item['method']} {item['path']} is implemented but not in the docs",
                    details={
                        "method": item["method"],
                        "path": item["path"],
                        "file_path": item["file_path"],
                        "line": item["line"],
                    },
                )
            )
    for item in documented:
        key = (item["method"], item["path"])
        if key not in implemented_keys:
            findings.append(
                _finding(
                    "route_missing_in_code",
                    "warning",
                    # The handler may simply live in a file that was never
                    # uploaded, so the index can only raise the question.
                    confirmed=False,
                    message=f"{item['method']} {item['path']} is documented but no handler was found",
                    details={"method": item["method"], "path": item["path"],
                             "readme_line": item["line"],
                             "reason": "the handler may be in a file that is not indexed"},
                )
            )
    return findings


def _table_findings(facts: ProjectFacts, readme: FileFacts) -> list[dict]:
    findings: list[dict] = []
    text = readme.text
    for table in tables(facts):
        if re.search(rf"\b{re.escape(table['table'])}\b", text):
            continue
        findings.append(
            _finding(
                "table_undocumented",
                "info",
                confirmed=True,
                message=f"Table {table['table']} has no mention in the README",
                details={"table": table["table"], "model": table["model"],
                         "file_path": table["file_path"]},
            )
        )
    return findings


def _setting_findings(facts: ProjectFacts) -> list[dict]:
    examples = [
        file
        for file in facts.files
        if file.name.lower() in {".env.example", ".env.sample", ".env.template"}
    ]
    if not examples:
        return []
    findings: list[dict] = []
    settings = Settings.model_fields
    # The examples themselves name every key, so they cannot be evidence that a
    # variable is read somewhere.
    example_paths = {example.path for example in examples}
    project_text = "\n".join(
        file.text for file in facts.files if file.path not in example_paths
    )
    for example in examples:
        declared = {match.group(1) for match in _ENV_KEY.finditer(example.text)}
        for name, field in settings.items():
            key = name.upper()
            if key in declared:
                continue
            if field.default is not None or not field.is_required():
                findings.append(
                    _finding(
                        "setting_undocumented",
                        "info",
                        confirmed=True,
                        message=f"{key} is a setting but missing from {example.path}",
                        details={"setting": name, "file_path": example.path},
                    )
                )
        for key in sorted(declared):
            if key in {name.upper() for name in settings}:
                continue
            if key in project_text:
                continue
            findings.append(
                _finding(
                    "setting_unused",
                    "info",
                    confirmed=False,
                    message=f"{example.path} declares {key}, which nothing in the project reads",
                    details={"variable": key, "file_path": example.path},
                )
            )
    return findings


def _link_findings(facts: ProjectFacts) -> list[dict]:
    known = {file.path for file in facts.files}
    findings: list[dict] = []
    for file in facts.files:
        if not file.name.lower().endswith(".md"):
            continue
        for number, line in enumerate(file.lines, start=1):
            for match in _MD_LINK.finditer(line):
                target = match.group(1).split("#", 1)[0].strip()
                if not target or "://" in target or target.startswith(("mailto:", "#")):
                    continue
                resolved = _resolve_link(file, target)
                if resolved in known:
                    continue
                findings.append(
                    _finding(
                        "doc_link_unresolved",
                        "info",
                        confirmed=False,
                        message=f"{file.path} links to {target}, which is not in the index",
                        details={"file_path": file.path, "line": number, "target": target},
                    )
                )
    return findings


def _resolve_link(file: FileFacts, target: str) -> str:
    parts = file.directory.split("/") if file.directory else []
    for part in target.replace("\\", "/").split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return "/".join(parts)


def _normalise_path(path: str) -> str:
    text = path.split("?", 1)[0].split("#", 1)[0].strip()
    text = re.sub(r"\{[^}]*\}", "{}", text)
    if text.startswith("/api/v1"):
        text = text[len("/api/v1"):] or "/"
    return text.rstrip("/") or "/"


def _finding(
    kind: str,
    severity: str,
    *,
    confirmed: bool,
    message: str,
    details: dict,
) -> dict:
    return {
        "kind": kind,
        "severity": severity,
        "confirmed": confirmed,
        "message": message,
        "details": details,
    }
