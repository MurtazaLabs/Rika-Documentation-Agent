"""Run the curated retrieval baseline against a live Rika API.

Start the API, index the repository as one project (ZIP upload is the easiest
way), then run from ``backend/``:

    ..\\.venv\\Scripts\\python.exe -m evaluation.run_retrieval_eval \
        --project-id <project-uuid>

No reranker is applied here; this measures the baseline hybrid retrieval.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

import httpx

from app.retrieval.evaluation import (
    CaseMetrics,
    ExpectedEvidence,
    evaluate_case,
    summarise,
)

DEFAULT_CASES = Path(__file__).with_name("retrieval_cases.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-id",
        required=True,
        help="Project whose indexed chunks are searched.",
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="API origin (default: http://127.0.0.1:8000).",
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=DEFAULT_CASES,
        help="Curated case file (default: retrieval_cases.json).",
    )
    parser.add_argument(
        "--mode",
        choices=("hybrid", "vector", "keyword"),
        default=None,
        help="Override each case's mode, for a vector/keyword baseline run.",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=10,
        help="Precision cutoff (1-50, default: 10). Recall@5/10 are always reported.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="HTTP timeout in seconds.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path for the JSON report.",
    )
    args = parser.parse_args()
    if not 1 <= args.k <= 50:
        parser.error("--k must be between 1 and 50")
    return args


async def run(args: argparse.Namespace) -> dict[str, Any]:
    payload = json.loads(args.cases.read_text(encoding="utf-8"))
    cases = payload["cases"] if isinstance(payload, dict) else payload
    rows: list[dict[str, Any]] = []
    metrics: list[CaseMetrics] = []

    async with httpx.AsyncClient(
        base_url=args.base_url.rstrip("/"), timeout=args.timeout
    ) as client:
        for case in cases:
            mode = args.mode or case.get("mode", "hybrid")
            request: dict[str, Any] = {
                "query": case["query"],
                "mode": mode,
                "limit": max(args.k, 10),
            }
            if case.get("filters"):
                request["filters"] = case["filters"]

            response = await client.post(
                f"/api/v1/projects/{args.project_id}/search", json=request
            )
            response.raise_for_status()
            results = response.json()["items"]
            expected = [
                ExpectedEvidence.from_mapping(item)
                for item in case["expected"]
            ]
            case_metrics = evaluate_case(results, expected, k=args.k)
            metrics.append(case_metrics)
            rows.append(
                {
                    "id": case["id"],
                    "query": case["query"],
                    "mode": mode,
                    "expected": [item for item in case["expected"]],
                    "returned": len(results),
                    **case_metrics.as_dict(),
                }
            )

    report = {
        "project_id": args.project_id,
        "base_url": args.base_url,
        "mode_override": args.mode,
        "cases": rows,
        "aggregate": summarise(metrics),
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return report


def main() -> None:
    args = parse_args()
    report = asyncio.run(run(args))
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
