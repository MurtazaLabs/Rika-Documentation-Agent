"""Project CRUD, validation and isolation tests."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.models import Document


async def _create_project(client: AsyncClient, name: str = "Rika") -> dict:
    response = await client.post(
        "/api/v1/projects", json={"name": name, "description": f"{name} project"}
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _add_document(
    factory: async_sessionmaker[AsyncSession],
    project_id: str,
    path: str,
) -> uuid.UUID:
    async with factory() as session:
        document = Document(
            project_id=uuid.UUID(project_id),
            original_path=path,
            stored_path=f"storage/extracted/{path}",
            filename=path.rsplit("/", 1)[-1],
            file_type="python",
            content_hash=f"hash-{path}",
            size=128,
            status="indexed",
        )
        session.add(document)
        await session.commit()
        return document.id


async def test_create_project(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/projects",
        json={"name": "  Rika  ", "description": "  Local RAG  "},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Rika"
    assert body["description"] == "Local RAG"
    assert body["settings"] == {}
    assert uuid.UUID(body["id"])
    assert body["created_at"] and body["updated_at"]


async def test_create_project_without_description(client: AsyncClient) -> None:
    response = await client.post("/api/v1/projects", json={"name": "Docs only"})

    assert response.status_code == 201
    assert response.json()["description"] is None


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "   "},
        {"name": ""},
        {"name": "x" * 201},
        {"name": "ok", "unexpected": True},
        {},
    ],
)
async def test_create_project_rejects_invalid_payload(
    client: AsyncClient, payload: dict
) -> None:
    response = await client.post("/api/v1/projects", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_list_projects(client: AsyncClient) -> None:
    for name in ("Alpha", "Beta", "Gamma"):
        await _create_project(client, name)

    response = await client.get("/api/v1/projects")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert sorted(item["name"] for item in body["items"]) == ["Alpha", "Beta", "Gamma"]
    assert body["limit"] == 50
    assert body["offset"] == 0


async def test_list_projects_paginates(client: AsyncClient) -> None:
    for name in ("Alpha", "Beta", "Gamma"):
        await _create_project(client, name)

    response = await client.get("/api/v1/projects", params={"limit": 2, "offset": 2})

    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 1


async def test_get_project(client: AsyncClient) -> None:
    created = await _create_project(client)

    response = await client.get(f"/api/v1/projects/{created['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


async def test_get_unknown_project_returns_404(client: AsyncClient) -> None:
    response = await client.get(f"/api/v1/projects/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_malformed_project_id_returns_422(client: AsyncClient) -> None:
    response = await client.get("/api/v1/projects/not-a-uuid")

    assert response.status_code == 422


async def test_update_project(client: AsyncClient) -> None:
    created = await _create_project(client)

    response = await client.patch(
        f"/api/v1/projects/{created['id']}", json={"name": "Renamed"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Renamed"
    assert body["description"] == created["description"]


async def test_update_can_clear_description(client: AsyncClient) -> None:
    created = await _create_project(client)

    response = await client.patch(
        f"/api/v1/projects/{created['id']}", json={"description": None}
    )

    assert response.status_code == 200
    assert response.json()["description"] is None


async def test_update_with_no_fields_is_rejected(client: AsyncClient) -> None:
    created = await _create_project(client)

    response = await client.patch(f"/api/v1/projects/{created['id']}", json={})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_delete_project(client: AsyncClient) -> None:
    created = await _create_project(client)

    response = await client.delete(f"/api/v1/projects/{created['id']}")

    assert response.status_code == 204
    assert response.content == b""
    assert (await client.get(f"/api/v1/projects/{created['id']}")).status_code == 404


async def test_delete_unknown_project_returns_404(client: AsyncClient) -> None:
    response = await client.delete(f"/api/v1/projects/{uuid.uuid4()}")

    assert response.status_code == 404


async def test_documents_are_isolated_between_projects(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    alpha = await _create_project(client, "Alpha")
    beta = await _create_project(client, "Beta")
    alpha_doc = await _add_document(session_factory, alpha["id"], "alpha/main.py")
    beta_doc = await _add_document(session_factory, beta["id"], "beta/main.py")

    alpha_list = (await client.get(f"/api/v1/projects/{alpha['id']}/documents")).json()
    beta_list = (await client.get(f"/api/v1/projects/{beta['id']}/documents")).json()

    assert alpha_list["total"] == 1
    assert [item["id"] for item in alpha_list["items"]] == [str(alpha_doc)]
    assert [item["original_path"] for item in alpha_list["items"]] == ["alpha/main.py"]

    assert beta_list["total"] == 1
    assert [item["id"] for item in beta_list["items"]] == [str(beta_doc)]


async def test_document_listing_requires_known_project(client: AsyncClient) -> None:
    response = await client.get(f"/api/v1/projects/{uuid.uuid4()}/documents")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_document_read_hides_server_path(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    project = await _create_project(client)
    document_id = await _add_document(session_factory, project["id"], "src/app.py")

    response = await client.get(f"/api/v1/documents/{document_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["original_path"] == "src/app.py"
    assert "stored_path" not in body


async def test_unknown_document_returns_404(client: AsyncClient) -> None:
    response = await client.get(f"/api/v1/documents/{uuid.uuid4()}")

    assert response.status_code == 404


async def test_deleting_project_removes_its_documents(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    project = await _create_project(client)
    document_id = await _add_document(session_factory, project["id"], "src/app.py")

    delete_response = await client.delete(f"/api/v1/projects/{project['id']}")
    assert delete_response.status_code == 204

    document_response = await client.get(f"/api/v1/documents/{document_id}")
    assert document_response.status_code == 404
