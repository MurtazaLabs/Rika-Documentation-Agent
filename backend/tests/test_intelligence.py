"""Project intelligence endpoints against an indexed sample project (§13)."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.ingestion.pipeline import run_ingestion
from tests.conftest import FakeEmbeddingClient
from tests.test_uploads import create_project, make_zip, quiet_queue

PROJECT_FILES = {
    "README.md": b"""# Widget service

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/widgets` | List widgets |

## Database

The `widgets` table stores widgets. The details live in [the guide](docs/guide.md).
""",
    "app/main.py": b"""from fastapi import FastAPI

from app.api.routes import widgets

app = FastAPI()
app.include_router(widgets.router)
""",
    "app/api/routes/widgets.py": b"""from fastapi import APIRouter

from app.services.widget_service import list_widgets

router = APIRouter(prefix="/widgets")


@router.get("")
def read_widgets() -> list[str]:
    \"\"\"Return every widget name.\"\"\"
    return list_widgets()
""",
    "app/services/widget_service.py": b"""from app.database.models.widget import Widget


def list_widgets() -> list[str]:
    \"\"\"Names of all widgets.\"\"\"
    return [widget.name for widget in Widget.all()]


def summarize(values: list[str]) -> str:
    cleaned = [value.strip() for value in values]
    joined = ", ".join(cleaned)
    if not joined:
        return "(none)"
    return joined.upper()
""",
    "app/legacy/duplicates.py": b"""def summarize_again(values: list[str]) -> str:
    cleaned = [value.strip() for value in values]
    joined = ", ".join(cleaned)
    if not joined:
        return "(none)"
    return joined.upper()
""",
    "app/database/models/widget.py": b"""from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Widget(Base):
    __tablename__ = "widgets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    owner_id: Mapped[int] = mapped_column(ForeignKey("owners.id"))
""",
    "app/legacy/broken.py": b"""from app.services.missing_module import helper


def broken_call() -> None:
    # TODO: remove this shim
    try:
        helper()
    except:
        pass
""",
    ".env.example": b"""APP_NAME=Rika
APP_ENV=production
WIDGET_TIMEOUT=5
""",
}


async def indexed_project(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    embeddings: FakeEmbeddingClient,
    monkeypatch: pytest.MonkeyPatch,
) -> str:
    quiet_queue(monkeypatch)
    project_id = await create_project(client, name="Widgets")
    response = await client.post(
        f"/api/v1/projects/{project_id}/upload-zip",
        files=[("file", ("project.zip", make_zip(PROJECT_FILES), "application/zip"))],
    )
    assert response.status_code == 201, response.text
    jobs = [uuid.UUID(job["id"]) for job in response.json()["jobs"]]
    assert len(jobs) == len(PROJECT_FILES)

    async with session_factory() as session:
        for job_id in jobs:
            result = await run_ingestion(session, job_id, settings, embeddings)
            assert result["status"] == "succeeded", result
    return project_id


async def test_a_project_without_files_reports_empty_analyses(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    quiet_queue(monkeypatch)
    project_id = await create_project(client, name="Empty")

    base = f"/api/v1/projects/{project_id}/intelligence"
    for path in ("overview", "architecture", "routes", "symbols", "docs", "findings"):
        response = await client.get(f"{base}/{path}")
        assert response.status_code == 200, (path, response.text)

    overview_body = (await client.get(f"{base}/overview")).json()
    assert overview_body["totals"] == {
        "files": 0,
        "code_files": 0,
        "symbols": 0,
        "languages": 0,
    }
    assert (await client.get(f"{base}/findings")).json()["findings"] == []


async def test_overview_describes_the_project(
    client: AsyncClient,
    app_settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    embeddings: FakeEmbeddingClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_id = await indexed_project(
        client, session_factory, app_settings, embeddings, monkeypatch
    )

    response = await client.get(f"/api/v1/projects/{project_id}/intelligence/overview")

    assert response.status_code == 200, response.text
    body = response.json()
    languages = {item["language"] for item in body["languages"]}
    assert {"python", "markdown"} <= languages
    frameworks = {item["name"] for item in body["frameworks"]}
    assert {"FastAPI", "SQLAlchemy"} <= frameworks
    assert body["entry_points"][0]["path"] == "app/main.py"
    assert body["entry_points"][0]["detail"] == "FastAPI application factory"
    config_paths = {item["path"] for item in body["config_files"]}
    assert ".env.example" in config_paths
    assert any(item["path"] == "app/services/widget_service.py"
               for item in body["important_modules"])
    assert body["dependencies"]["internal_edges"] > 0


async def test_architecture_layers_edges_tables_and_flows(
    client: AsyncClient,
    app_settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    embeddings: FakeEmbeddingClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_id = await indexed_project(
        client, session_factory, app_settings, embeddings, monkeypatch
    )

    response = await client.get(
        f"/api/v1/projects/{project_id}/intelligence/architecture"
    )

    assert response.status_code == 200, response.text
    body = response.json()
    layers = {layer["name"] for layer in body["layers"]}
    assert {"API routes", "Services", "Database"} <= layers
    edges = {(edge["source"], edge["target"]) for edge in body["edges"]}
    assert ("API routes", "Services") in edges

    widget = next(table for table in body["database"]["tables"] if table["table"] == "widgets")
    assert widget["model"] == "Widget"
    assert {"id", "name", "owner_id"} <= set(widget["columns"])
    assert widget["references"] == ["owners"]

    flow = next(flow for flow in body["request_flows"] if flow["path"] == "/widgets")
    assert flow["method"] == "GET"
    assert flow["handler"] == "read_widgets"
    assert "app/services/widget_service.py" in flow["imports"]

    routed = await client.get(
        f"/api/v1/projects/{project_id}/intelligence/routes", params={"method": "POST"}
    )
    assert routed.status_code == 200
    assert routed.json() == []


async def test_symbol_search_and_explanation(
    client: AsyncClient,
    app_settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    embeddings: FakeEmbeddingClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_id = await indexed_project(
        client, session_factory, app_settings, embeddings, monkeypatch
    )

    response = await client.get(
        f"/api/v1/projects/{project_id}/intelligence/symbols",
        params={"q": "list_widgets", "symbol_type": "function"},
    )

    assert response.status_code == 200, response.text
    hits = response.json()
    assert [hit["name"] for hit in hits] == ["list_widgets"]
    symbol_id = hits[0]["id"]

    detail = await client.get(
        f"/api/v1/projects/{project_id}/intelligence/symbols/{symbol_id}"
    )

    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert "def list_widgets" in body["definition"]
    assert body["doc"] == "Names of all widgets."
    assert body["imported_by"] == ["app/api/routes/widgets.py"]
    references = {(item["path"], item["line"]) for item in body["references"]}
    assert any(path == "app/api/routes/widgets.py" for path, _ in references)

    imports = await client.get(
        f"/api/v1/projects/{project_id}/intelligence/imports",
        params={"path": "app/api/routes/widgets.py"},
    )
    assert imports.status_code == 200, imports.text
    resolved = {
        item["reference"]: item["resolved_path"] for item in imports.json()["imports"]
    }
    assert resolved["app.services.widget_service"] == "app/services/widget_service.py"

    missing = await client.get(
        f"/api/v1/projects/{project_id}/intelligence/symbols/{uuid.uuid4()}"
    )
    assert missing.status_code == 404


async def test_docs_comparison_and_findings(
    client: AsyncClient,
    app_settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    embeddings: FakeEmbeddingClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_id = await indexed_project(
        client, session_factory, app_settings, embeddings, monkeypatch
    )

    docs = await client.get(f"/api/v1/projects/{project_id}/intelligence/docs")
    assert docs.status_code == 200, docs.text
    report = docs.json()
    assert report["readme"] == "README.md"
    assert report["routes"] == {"documented": 1, "implemented": 1}
    kinds = {finding["kind"] for finding in report["findings"]}
    assert "doc_link_unresolved" in kinds
    assert "setting_unused" in kinds
    assert "route_missing_in_docs" not in kinds

    findings = await client.get(f"/api/v1/projects/{project_id}/intelligence/findings")
    assert findings.status_code == 200, findings.text
    report = findings.json()
    by_kind: dict[str, list[dict]] = {}
    for finding in report["findings"]:
        by_kind.setdefault(finding["kind"], []).append(finding)
    broken = by_kind["broken_import"]
    assert all(finding["confidence"] == "confirmed" for finding in broken)
    assert any(
        "missing_module" in finding["details"]["reference"] for finding in broken
    )
    assert by_kind["bare_except"][0]["confidence"] == "confirmed"
    assert "duplicate_implementation" in by_kind
    assert "unresolved_marker" in by_kind
    assert by_kind["config_default_mismatch"][0]["details"]["key"] == "APP_ENV"
    assert report["summary"]["confirmed"] == sum(
        1 for finding in report["findings"] if finding["confidence"] == "confirmed"
    )
