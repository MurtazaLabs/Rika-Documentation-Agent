"""Client for local model servers.

Targets llama.cpp's ``llama-server``, which exposes an OpenAI-compatible API.
Any server implementing ``/v1/models``, ``/v1/embeddings`` and
``/v1/chat/completions`` works (for example Ollama). Chat completions are
available both as a single response and as a stream of content deltas.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator, Sequence

import httpx

from app.core.exceptions import ModelServerError

logger = logging.getLogger(__name__)

ChatMessage = dict[str, str]


class ModelServerClient:
    """Thin async wrapper around one model server."""

    def __init__(
        self,
        base_url: str,
        model_name: str,
        *,
        timeout: float = 30.0,
        client: httpx.AsyncClient | None = None,
        max_concurrency: int = 1,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.timeout = timeout
        self._client = client
        self._owns_client = client is None
        # One slot on a 4 GB card: the server has no room for parallel
        # generations, so extra work waits here instead of thrashing VRAM.
        self.max_concurrency = max(1, max_concurrency)
        self._slots: asyncio.Semaphore | None = None

    def _semaphore(self) -> asyncio.Semaphore:
        """Created on first use: a primitive made at import time would bind to
        whichever loop happened to load the module (tests use one per case)."""
        if self._slots is None:
            self._slots = asyncio.Semaphore(self.max_concurrency)
        return self._slots

    # -- lifecycle ---------------------------------------------------------
    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url, timeout=self.timeout
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    # -- requests ----------------------------------------------------------
    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        async with self._semaphore():
            return await self._send(method, path, **kwargs)

    async def _send(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = await self._http().request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise ModelServerError(
                f"{self.base_url}{path} is unreachable: {exc.__class__.__name__}"
            ) from exc

        if response.status_code >= 400:
            body = response.text.strip()[:300]
            raise ModelServerError(
                f"{self.base_url}{path} returned {response.status_code}: {body}"
            )
        try:
            return response.json()
        except ValueError as exc:
            raise ModelServerError(
                f"{self.base_url}{path} returned non-JSON content"
            ) from exc

    # -- API ---------------------------------------------------------------
    async def list_models(self) -> list[str]:
        """Return the model ids the server has loaded."""
        payload = await self._request("GET", "/v1/models")
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list):
            raise ModelServerError(f"{self.base_url} returned an unexpected /v1/models payload")
        return [str(item.get("id", "")) for item in data if isinstance(item, dict)]

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed one or more texts; returns one vector per input."""
        if not texts:
            return []
        payload = await self._request(
            "POST",
            "/v1/embeddings",
            json={"model": self.model_name, "input": list(texts)},
        )
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list) or len(data) != len(texts):
            raise ModelServerError(f"{self.base_url} returned an unexpected /v1/embeddings payload")
        vectors: list[list[float]] = []
        for item in sorted(data, key=lambda entry: entry.get("index", 0)):
            vector = item.get("embedding") if isinstance(item, dict) else None
            if not isinstance(vector, list) or not vector:
                raise ModelServerError(f"{self.base_url} returned an empty embedding")
            vectors.append([float(value) for value in vector])
        return vectors

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int = 512,
    ) -> str:
        """Non-streaming completion."""
        payload = await self._request(
            "POST",
            "/v1/chat/completions",
            json={
                "model": self.model_name,
                "messages": list(messages),
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False,
            },
        )
        choices = payload.get("choices") if isinstance(payload, dict) else None
        if not isinstance(choices, list) or not choices:
            raise ModelServerError(f"{self.base_url} returned no choices")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not isinstance(content, str):
            raise ModelServerError(f"{self.base_url} returned an empty completion")
        return content

    async def chat_stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int = 512,
    ) -> AsyncIterator[str]:
        """Yield content deltas, holding a slot for the whole generation."""
        async with self._semaphore():
            async for chunk in self._stream(
                messages, temperature=temperature, max_tokens=max_tokens
            ):
                yield chunk

    async def _stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int = 512,
    ) -> AsyncIterator[str]:
        """Yield content deltas from an OpenAI-compatible SSE completion.

        llama.cpp sends one ``data: {json}`` event per token batch and ends
        with ``data: [DONE]``. Errors raised before the first delta propagate
        normally; the chat service turns later ones into a stream error event.
        """
        request = {
            "model": self.model_name,
            "messages": list(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        try:
            async with self._http().stream(
                "POST", "/v1/chat/completions", json=request
            ) as response:
                if response.status_code >= 400:
                    body = (await response.aread()).decode(
                        "utf-8", errors="replace"
                    ).strip()[:300]
                    raise ModelServerError(
                        f"{self.base_url}/v1/chat/completions returned "
                        f"{response.status_code}: {body}"
                    )

                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line or line.startswith(":"):
                        continue
                    if not line.startswith("data:"):
                        continue
                    data = line[len("data:") :].strip()
                    if data == "[DONE]":
                        return
                    try:
                        event = json.loads(data)
                    except ValueError as exc:
                        raise ModelServerError(
                            f"{self.base_url} sent malformed stream data"
                        ) from exc

                    if isinstance(event, dict) and event.get("error"):
                        error = event["error"]
                        detail = (
                            error.get("message")
                            if isinstance(error, dict)
                            else str(error)
                        )
                        raise ModelServerError(
                            f"{self.base_url} streamed an error: "
                            f"{str(detail)[:300]}"
                        )

                    choices = (
                        event.get("choices") if isinstance(event, dict) else None
                    )
                    if not isinstance(choices, list) or not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    content = delta.get("content")
                    if isinstance(content, str) and content:
                        yield content
        except httpx.HTTPError as exc:
            raise ModelServerError(
                f"{self.base_url}/v1/chat/completions is unreachable: "
                f"{exc.__class__.__name__}"
            ) from exc
