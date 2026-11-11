"""Health endpoint and readiness aggregation tests.

These run without PostgreSQL, Redis or model servers: probes are expected to
fail here, and readiness must report that rather than raising.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.schemas.health import DependencyCheck
from app.main import app


def _check(name: str, status: str, critical: bool = True) -> DependencyCheck:
    return DependencyCheck(name=name, status=status, critical=critical)  # type: ignore[arg-type]


def test_liveness_reports_alive() -> None:
    with TestClient(app) as client:
        response = client.get("/health/live")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "alive"
    assert body["app"] == "Rika"
    assert body["version"]


def test_request_id_header_is_echoed() -> None:
    with TestClient(app) as client:
        response = client.get("/health/live", headers={"X-Request-ID": "abc123"})

    assert response.headers["X-Request-ID"] == "abc123"


def test_request_id_is_generated_when_absent() -> None:
    with TestClient(app) as client:
        response = client.get("/health/live")

    assert response.headers.get("X-Request-ID")


def test_readiness_reports_every_dependency() -> None:
    with TestClient(app) as client:
        response = client.get("/health/ready")

    body = response.json()
    assert response.status_code in (200, 503)
    assert {check["name"] for check in body["checks"]} == {
        "postgres",
        "redis",
        "chat_model",
        "embedding_model",
        "worker",
    }
    assert body["status"] in {"ready", "degraded", "unavailable"}
    # 503 means a critical dependency is down.
    assert (response.status_code == 503) == (body["status"] == "unavailable")


def test_evaluate_status_ready_when_all_ok() -> None:
    from app.services.system_service import evaluate_status

    checks = [
        _check("postgres", "ok"),
        _check("redis", "ok"),
        _check("chat_model", "ok", critical=False),
    ]
    assert evaluate_status(checks) == "ready"


def test_evaluate_status_degraded_when_model_down() -> None:
    from app.services.system_service import evaluate_status

    checks = [
        _check("postgres", "ok"),
        _check("redis", "ok"),
        _check("embedding_model", "error", critical=False),
    ]
    assert evaluate_status(checks) == "degraded"


def test_evaluate_status_unavailable_when_critical_down() -> None:
    from app.services.system_service import evaluate_status

    checks = [
        _check("postgres", "error"),
        _check("redis", "ok"),
        _check("chat_model", "error", critical=False),
    ]
    assert evaluate_status(checks) == "unavailable"


async def test_worker_probe_reports_online(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.system_service import check_worker
    from app.workers.celery_app import celery_app

    monkeypatch.setattr(
        celery_app.control,
        "ping",
        lambda timeout=None: [{"celery@test": {"ok": "pong"}}],
    )

    check = await check_worker(timeout=0.1)

    assert check.status == "ok"
    assert check.critical is False
    assert check.detail == "1 worker online"


async def test_worker_probe_reports_an_empty_queue(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.system_service import check_worker
    from app.workers.celery_app import celery_app

    monkeypatch.setattr(celery_app.control, "ping", lambda timeout=None: [])

    check = await check_worker(timeout=0.1)

    assert check.status == "error"
    assert check.critical is False
    assert "stay queued" in (check.detail or "")


def test_unknown_route_returns_404() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/nope")

    assert response.status_code == 404
