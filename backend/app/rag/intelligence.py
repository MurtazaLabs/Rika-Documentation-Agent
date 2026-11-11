"""Derived project-intelligence items as a second evidence channel for chat.

Chat normally answers from retrieved chunks. Questions about architecture or
defects often have their answer in a report rather than in a passage, so the
reports from ``app.intelligence`` are rendered into the prompt with their own
``[I#]`` markers. Only the items that fit the prompt are offered, and markers
that name something the model was never shown are removed afterwards, exactly
as ``app.rag.citations`` treats ``[S#]``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.intelligence import architecture, docs_check, findings, overview
from app.intelligence.facts import ProjectFacts

MAX_ITEMS = 24
MAX_FINDINGS = 12
MAX_CONFIRMED_DOC_FINDINGS = 3

_MARKER_GROUP = re.compile(r"\[((?:I\d+)(?:\s*[,;]\s*I\d+)*)\]", re.IGNORECASE)
_MARKER = re.compile(r"I(\d+)", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class IntelligenceItem:
    """One derived fact, citable as ``[I#]`` while it is in the prompt.

    ``confidence`` is the report's own label: ``confirmed`` means the index
    settles the question, ``possible`` means a human still has to look. The
    prompt tells the model never to present a ``possible`` item as a fact.
    """

    marker: str
    kind: str
    message: str
    confidence: str | None = None
    severity: str | None = None
    file_path: str | None = None
    line: int | None = None

    def prompt_line(self) -> str:
        tags = " ".join(
            f"{label}={value}"
            for label, value in (
                ("kind", self.kind),
                ("confidence", self.confidence),
                ("severity", self.severity),
            )
            if value
        )
        location = ""
        if self.file_path:
            location = f" at {self.file_path}"
            if self.line:
                location = f"{location}:{self.line}"
        return f"[{self.marker}] ({tags}) {_one_line(self.message)}{location}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "marker": self.marker,
            "kind": self.kind,
            "message": self.message,
            "confidence": self.confidence,
            "severity": self.severity,
            "file_path": self.file_path,
            "line": self.line,
        }


@dataclass(slots=True)
class IntelligenceValidation:
    """The cleaned answer plus the derived items that survived validation."""

    text: str
    items: list[dict[str, Any]]
    invalid_markers: list[str]


def build_intelligence(facts: ProjectFacts) -> list[IntelligenceItem]:
    """The citable derived facts for a project, most structural first."""
    return [
        IntelligenceItem(marker=f"I{number}", **candidate)
        for number, candidate in enumerate(_candidates(facts)[:MAX_ITEMS], start=1)
    ]


def validate_intelligence(
    text: str, items: list[IntelligenceItem]
) -> IntelligenceValidation:
    """Resolve ``[I#]`` markers, then remove them from the answer.

    Markers are prompt wiring, not something the reader can open: a derived
    item has no chunk to highlight and is not persisted with the message. The
    cited items are returned beside the answer instead, ordered by first
    mention, so the prose reads cleanly and no marker can dangle later.
    """
    by_marker = {item.marker.upper(): item for item in items}
    cited: list[IntelligenceItem] = []
    seen: set[str] = set()
    invalid: list[str] = []

    def _replace(group: re.Match[str]) -> str:
        for raw in _MARKER.findall(group.group(1)):
            marker = f"I{int(raw)}"
            key = marker.upper()
            if key not in by_marker:
                invalid.append(marker)
                continue
            if key not in seen:
                seen.add(key)
                cited.append(by_marker[key])
        return ""

    cleaned = _MARKER_GROUP.sub(_replace, text)
    # Removing a marker can leave a space before punctuation.
    cleaned = re.sub(r"[ \t]+([.,;:!?])", r"\1", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned).strip()

    return IntelligenceValidation(
        text=cleaned,
        items=[item.as_dict() for item in cited],
        invalid_markers=sorted(set(invalid), key=_marker_number),
    )


def _candidates(facts: ProjectFacts) -> list[dict[str, Any]]:
    architecture_report = architecture.architecture(facts)
    overview_report = overview.overview(facts)
    findings_report = findings.investigate(facts)
    docs_report = docs_check.compare(facts)

    candidates: list[dict[str, Any]] = []

    for layer in architecture_report["layers"][:8]:
        candidates.append(
            {
                "kind": "layer",
                "message": (
                    f"{layer['name']} layer ({layer['side']}): {layer['files']} files, "
                    f"{layer['symbols']} symbols, {layer['imports_out']} imports out, "
                    f"imported by {layer['imported_by']}"
                ),
            }
        )

    for edge in architecture_report["edges"][:6]:
        candidates.append(
            {
                "kind": "dependency",
                "message": (
                    f"{edge['source']} -> {edge['target']}: {edge['count']} imports"
                ),
            }
        )

    for module in overview_report["important_modules"][:5]:
        candidates.append(
            {
                "kind": "module",
                "message": (
                    f"{module['path']} ({module['layer']}) has "
                    f"{module['symbols']} symbols and is imported by "
                    f"{module['imported_by']}"
                ),
                "file_path": module["path"],
            }
        )

    for table in architecture_report["database"]["tables"][:10]:
        candidates.append(
            {
                "kind": "table",
                "message": (
                    f"table {table['table']} ({table['model'] or 'no model class'}) "
                    f"has {len(table['columns'])} columns"
                ),
                "file_path": table["file_path"],
                "line": table["line"],
            }
        )

    for finding in findings_report["findings"][:MAX_FINDINGS]:
        details = finding["details"]
        candidates.append(
            {
                "kind": finding["kind"],
                "message": finding["message"],
                "confidence": finding["confidence"],
                "severity": finding["severity"],
                "file_path": _text(details.get("file_path")),
                "line": _line(details.get("line")),
            }
        )

    routes = docs_report["routes"]
    if routes["documented"] or routes["implemented"]:
        candidates.append(
            {
                "kind": "documentation",
                "message": (
                    f"the docs describe {routes['documented']} routes and the code "
                    f"implements {routes['implemented']}"
                ),
            }
        )

    confirmed_docs = [
        finding for finding in docs_report["findings"] if finding["confirmed"]
    ]
    for finding in confirmed_docs[:MAX_CONFIRMED_DOC_FINDINGS]:
        details = finding["details"]
        candidates.append(
            {
                "kind": finding["kind"],
                "message": finding["message"],
                "confidence": "confirmed",
                "severity": finding["severity"],
                "file_path": _text(details.get("file_path")),
                "line": _line(details.get("line")),
            }
        )

    return candidates


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _line(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _one_line(text: str) -> str:
    return " ".join(text.split())


def _marker_number(marker: str) -> int:
    match = _MARKER.fullmatch(marker)
    return int(match.group(1)) if match else 0
