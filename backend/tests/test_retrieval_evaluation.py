"""Retrieval evaluation metrics and the curated case file."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.retrieval.evaluation import (
    CaseMetrics,
    ExpectedEvidence,
    citation_correctness,
    citation_is_correct,
    duplicate_frequency,
    evaluate_case,
    evidence_matches,
    precision_at_k,
    recall_at_k,
    summarise,
)


def _results() -> list[dict]:
    return [
        {
            "chunk_id": "a",
            "file_path": "src/tax.py",
            "content": "def calculate_tax(amount):\n    return amount * 0.2",
            "content_type": "code",
            "language": "python",
            "symbol_name": "calculate_tax",
            "start_line": 1,
            "end_line": 2,
        },
        {
            "chunk_id": "b",
            "file_path": "docs/guide.md",
            "content": "Tax guide and examples.",
            "content_type": "document",
            "language": None,
            "symbol_name": None,
            "start_line": None,
            "end_line": None,
        },
        {
            "chunk_id": "c",
            "file_path": "src/tax.py",
            "content": "def calculate_tax(amount):\n    return amount * 0.2",
            "content_type": "code",
            "language": "python",
            "symbol_name": "calculate_tax",
            "start_line": 1,
            "end_line": 2,
        },
    ]


def test_recall_and_precision_use_expected_evidence() -> None:
    results = _results()
    expected = [
        ExpectedEvidence(
            file_path="src/tax.py", symbol_name="calculate_tax"
        ),
        ExpectedEvidence(file_path="docs/guide.md"),
    ]

    assert recall_at_k(results, expected, 1) == pytest.approx(0.5)
    assert recall_at_k(results, expected, 5) == pytest.approx(1.0)
    assert recall_at_k(results, expected, 10) == pytest.approx(1.0)
    assert precision_at_k(results, expected, 1) == pytest.approx(1.0)
    assert precision_at_k(results, expected, 2) == pytest.approx(1.0)
    assert precision_at_k(results, expected, 10) == pytest.approx(1.0)


def test_line_and_page_evidence_must_overlap() -> None:
    result = {
        "file_path": "src/tax.py",
        "symbol_name": "calculate_tax",
        "start_line": 10,
        "end_line": 20,
        "page_number": 3,
    }

    assert evidence_matches(
        result,
        ExpectedEvidence(
            file_path="src/tax.py", start_line=15, end_line=25
        ),
    )
    assert not evidence_matches(
        result,
        ExpectedEvidence(
            file_path="src/tax.py", start_line=21, end_line=30
        ),
    )
    assert evidence_matches(
        result,
        ExpectedEvidence(file_path="src/tax.py", page_number=3),
    )
    assert not evidence_matches(
        result,
        ExpectedEvidence(file_path="src/tax.py", page_number=4),
    )


def test_citation_correctness_and_duplicate_frequency() -> None:
    results = _results()

    assert citation_correctness(results) == pytest.approx(1.0)
    assert duplicate_frequency(results) == pytest.approx(1 / 3)
    assert not citation_is_correct(
        {
            "file_path": "src/tax.py",
            "content_type": "code",
            "language": "python",
            "start_line": 5,
            "end_line": 2,
        }
    )
    assert not citation_is_correct(
        {
            "file_path": "docs/guide.md",
            "content_type": "document",
            "page_number": 0,
        }
    )
    assert not citation_is_correct(
        {"file_path": "src/tax.py", "content_type": "code"}
    )


def test_evaluate_case_and_summary() -> None:
    metrics = evaluate_case(
        _results(),
        [ExpectedEvidence(file_path="src/tax.py")],
        k=2,
    )

    assert isinstance(metrics, CaseMetrics)
    summary = summarise([metrics, metrics])
    assert summary["recall@5"] == pytest.approx(1.0)
    assert summary["recall@10"] == pytest.approx(1.0)
    assert summary["precision"] == pytest.approx(0.5)
    assert summary["citation_correctness"] == pytest.approx(1.0)
    assert summary["duplicate_frequency"] == pytest.approx(1 / 3)


def test_empty_results_score_zero() -> None:
    expected = [ExpectedEvidence(file_path="src/tax.py")]

    assert recall_at_k([], expected, 5) == 0.0
    assert precision_at_k([], expected, 5) == 0.0
    assert citation_correctness([]) == 0.0
    assert duplicate_frequency([]) == 0.0
    assert summarise([])["recall@5"] == 0.0


def test_curated_cases_reference_real_files() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    payload = json.loads(
        (repo_root / "backend/evaluation/retrieval_cases.json").read_text(
            encoding="utf-8"
        )
    )
    cases = payload["cases"]

    assert len(cases) >= 10
    assert len({case["id"] for case in cases}) == len(cases)
    for case in cases:
        assert case["query"].strip()
        assert case["expected"]
        for evidence in case["expected"]:
            path = repo_root / evidence["file_path"]
            assert path.is_file(), evidence["file_path"]
