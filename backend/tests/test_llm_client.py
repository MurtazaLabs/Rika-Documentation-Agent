"""Local model server client: completion and SSE streaming."""

from __future__ import annotations

import json

import httpx
import pytest

from app.core.exceptions import ModelServerError
from app.llm.llama_client import ModelServerClient


def stream_response(*events: str, status_code: int = 200) -> httpx.Response:
    body = "".join(f"data: {event}\n\n" for event in events)
    return httpx.Response(
        status_code,
        text=body,
        headers={"content-type": "text/event-stream"},
    )


async def test_chat_stream_parses_deltas_and_stops_at_done() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["stream"] is True
        assert payload["messages"] == [{"role": "user", "content": "hi"}]
        return stream_response(
            '{"choices":[{"delta":{"role":"assistant"}}]}',
            '{"choices":[{"delta":{"content":"Hello"}}]}',
            '{"choices":[{"delta":{"content":" world"}}]}',
            "[DONE]",
            '{"choices":[{"delta":{"content":"ignored"}}]}',
        )

    http = httpx.AsyncClient(base_url="http://model", transport=httpx.MockTransport(handler))
    model = ModelServerClient("http://model", "test-model", client=http)
    try:
        chunks = [
            chunk
            async for chunk in model.chat_stream(
                [{"role": "user", "content": "hi"}]
            )
        ]
    finally:
        await http.aclose()

    assert chunks == ["Hello", " world"]


async def test_chat_stream_reports_http_errors() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="model exploded")

    http = httpx.AsyncClient(base_url="http://model", transport=httpx.MockTransport(handler))
    model = ModelServerClient("http://model", "test-model", client=http)
    try:
        with pytest.raises(ModelServerError) as caught:
            _ = [
                chunk
                async for chunk in model.chat_stream(
                    [{"role": "user", "content": "hi"}]
                )
            ]
    finally:
        await http.aclose()

    assert "500" in str(caught.value)
    assert "model exploded" in str(caught.value)


async def test_chat_stream_reports_malformed_data() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return stream_response("not-json")

    http = httpx.AsyncClient(base_url="http://model", transport=httpx.MockTransport(handler))
    model = ModelServerClient("http://model", "test-model", client=http)
    try:
        with pytest.raises(ModelServerError):
            _ = [
                chunk
                async for chunk in model.chat_stream(
                    [{"role": "user", "content": "hi"}]
                )
            ]
    finally:
        await http.aclose()


async def test_chat_stream_reports_unreachable_server() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route", request=request)

    http = httpx.AsyncClient(base_url="http://model", transport=httpx.MockTransport(handler))
    model = ModelServerClient("http://model", "test-model", client=http)
    try:
        with pytest.raises(ModelServerError):
            _ = [
                chunk
                async for chunk in model.chat_stream(
                    [{"role": "user", "content": "hi"}]
                )
            ]
    finally:
        await http.aclose()


async def test_non_streaming_chat_returns_content() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["stream"] is False
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "The answer [S1]."}}]},
        )

    http = httpx.AsyncClient(base_url="http://model", transport=httpx.MockTransport(handler))
    model = ModelServerClient("http://model", "test-model", client=http)
    try:
        answer = await model.chat([{"role": "user", "content": "hi"}])
    finally:
        await http.aclose()

    assert answer == "The answer [S1]."
