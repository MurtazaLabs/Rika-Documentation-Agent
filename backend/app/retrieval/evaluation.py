"""Metric helpers for the curated retrieval evaluation.

The baseline is evaluated on ranked search results, not on generated answers:
Recall@5/10, precision@k, citation correctness and duplicate frequency. The
curated cases live in ``backend/evaluation/retrieval_cases.json`` and the
runner is ``backend/evaluation/run_retrieval_eval.py``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields
from typing import Any

Truth = Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ExpectedEvidence:
    """One source the evaluation case expects to be retrieved."""

    file_path: str
    symbol_name: str | None = None
    page_number: int | None = None
    start_line: int | None = None
    end_line: int | None = None

    @classmethod
    def from_mapping(cls, value: Truth) -> ExpectedEvidence:
        known = {field.name for field in fields(cls)}
        return cls(**{key: item for key, item in value.items() if key in known})


@dataclass(frozen=True, slots=True)
class CaseMetrics:
    recall_at_5: float
    recall_at_10: float
    precision_at_k: float
    citation_correctness: float
    duplicate_frequency: float

    def as_dict(self) -> dict[str, float]:
        return {
            "recall@5": self.recall_at_5,
            "recall@10": self.recall_at_10,
            "precision": self.precision_at_k,
            "citation_correctness": self.citation_correctness,
            "duplicate_frequency": self.duplicate_frequency,
        }


def evidence_matches(result: Truth, expected: ExpectedEvidence) -> bool:
    """Whether one result cites the expected file/symbol/page/line range."""
    if _normalise_path(str(result.get("file_path") or "")) != _normalise_path(
        expected.file_path
    ):
        return False

    if expected.symbol_name is not None:
        if result.get("symbol_name") != expected.symbol_name:
            return False

    if expected.page_number is not None:
        if _as_int(result.get("page_number")) != expected.page_number:
            return False

    if expected.start_line is not None or expected.end_line is not None:
        start = _as_int(result.get("start_line"))
        end = _as_int(result.get("end_line"))
        if start is None or end is None:
            return False
        expected_start = (
            expected.start_line
            if expected.start_line is not None
            else expected.end_line
        )
        expected_end = (
            expected.end_line
            if expected.end_line is not None
            else expected_start
        )
        if expected_start is None or expected_end is None:
            return False
        if start > expected_end or end < expected_start:
            return False

    return True


def recall_at_k(
    results: Sequence[Truth], expected: Sequence[ExpectedEvidence], k: int
) -> float:
    """Fraction of expected evidence items found in the top ``k`` results."""
    if not expected:
        return 1.0
    top = list(results[: max(k, 0)])
    found = sum(
        1
        for evidence in expected
        if any(evidence_matches(result, evidence) for result in top)
    )
    return found / len(expected)


def precision_at_k(
    results: Sequence[Truth], expected: Sequence[ExpectedEvidence], k: int
) -> float:
    """Fraction of returned top-``k`` results that cite expected evidence."""
    top = list(results[: max(k, 0)])
    if not top:
        return 0.0
    relevant = sum(
        1
        for result in top
        if any(evidence_matches(result, evidence) for evidence in expected)
    )
    return relevant / len(top)


def citation_is_correct(result: Truth) -> bool:
    """Whether a result carries the citation fields its content type needs.

    Code needs a language and a valid line range (symbol chunks also carry the
    symbol name); documents always need a file path, and a page number when
    one is present must be positive.
    """
    if not result.get("file_path") or not result.get("content_type"):
        return False

    page_number = result.get("page_number")
    if page_number is not None:
        page = _as_int(page_number)
        if page is None or page < 1:
            return False

    if result.get("content_type") != "code":
        return True

    if not result.get("language"):
        return False
    start = _as_int(result.get("start_line"))
    end = _as_int(result.get("end_line"))
    return start is not None and end is not None and 1 <= start <= end


def citation_correctness(results: Sequence[Truth]) -> float:
    """Fraction of returned results with complete, valid citations."""
    if not results:
        return 0.0
    return sum(1 for result in results if citation_is_correct(result)) / len(
        results
    )


def duplicate_frequency(results: Sequence[Truth]) -> float:
    """Fraction of results repeating an earlier file path and content."""
    if not results:
        return 0.0
    keys = [_content_key(result) for result in results]
    return 1.0 - (len(set(keys)) / len(keys))


def evaluate_case(
    results: Sequence[Truth],
    expected: Sequence[ExpectedEvidence],
    *,
    k: int = 10,
) -> CaseMetrics:
    """Compute every metric for one query's ranked results."""
    return CaseMetrics(
        recall_at_5=recall_at_k(results, expected, 5),
        recall_at_10=recall_at_k(results, expected, 10),
        precision_at_k=precision_at_k(results, expected, k),
        citation_correctness=citation_correctness(results),
        duplicate_frequency=duplicate_frequency(results),
    )


def summarise(cases: Sequence[CaseMetrics]) -> dict[str, float]:
    """Arithmetic mean of each metric across all evaluation cases."""
    if not cases:
        return {
            "recall@5": 0.0,
            "recall@10": 0.0,
            "precision": 0.0,
            "citation_correctness": 0.0,
            "duplicate_frequency": 0.0,
        }
    keys = cases[0].as_dict().keys()
    return {
        key: sum(case.as_dict()[key] for case in cases) / len(cases)
        for key in keys
    }


def _content_key(result: Truth) -> tuple[str, str]:
    content = re.sub(
        r"\s+", " ", str(result.get("content") or "")
    ).strip().casefold()
    if not content:
        return ("chunk", str(result.get("chunk_id") or ""))
    return (_normalise_path(str(result.get("file_path") or "")), content)


def _normalise_path(value: str) -> str:
    path = value.strip().replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    return path.rstrip("/")


def _as_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None
