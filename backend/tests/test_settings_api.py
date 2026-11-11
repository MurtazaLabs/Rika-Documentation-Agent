"""The settings endpoint exposes configuration but never credentials."""

from __future__ import annotations

import json

from httpx import AsyncClient


async def test_settings_returns_safe_runtime_configuration(client: AsyncClient) -> None:
    response = await client.get("/api/v1/settings")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["app_name"] == "Rika"
    assert body["editable"] is False
    assert body["chat"]["model_name"]
    assert body["embedding"]["model_name"]
    assert body["storage"]["max_upload_mb"] == 2
    assert body["indexing"]["chunk_overlap_chars"] == 60

    serialized = json.dumps(body).lower()
    assert "database_url" not in serialized
    assert "redis_url" not in serialized
    assert "postgresql+asyncpg" not in serialized
    assert "change-me" not in serialized
