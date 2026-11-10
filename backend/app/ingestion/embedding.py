"""Embedding step of the ingestion pipeline.

Chunk text goes to the local embedding server in batches and comes back as
vectors that must match the width of the ``document_chunks.embedding`` column.
Nothing here touches the database: the pipeline stores what this returns, so a
failed or wrong-shaped request can be rejected before any row changes.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Iterator, Sequence

from app.llm.llama_client import ModelServerClient

logger = logging.getLogger("rika.ingestion")


class EmbeddingError(RuntimeError):
    """The embedding step could not produce usable vectors."""


# Called with (texts_done, texts_total) after each batch.
ProgressCallback = Callable[[int, int], Awaitable[None]]


def batch_texts(
    texts: Sequence[str], *, batch_size: int, max_chars: int = 24_000
) -> Iterator[tuple[int, list[str]]]:
    """Yield ``(start_index, batch)`` covering ``texts`` in order.

    Batches are split on both count and total characters: llama-server scales
    work with tokens, and sixteen maximum-size chunks can otherwise exceed its
    slot context even though the batch is small by count.
    """
    if batch_size < 1:
        raise ValueError("batch_size must be positive")

    start = 0
    while start < len(texts):
        stop = start
        budget = 0
        while stop < len(texts) and stop - start < batch_size:
            cost = len(texts[stop])
            if stop > start and budget + cost > max_chars:
                break
            budget += cost
            stop += 1
        yield start, list(texts[start:stop])
        start = stop


async def embed_texts(
    client: ModelServerClient,
    texts: Sequence[str],
    *,
    dimension: int,
    batch_size: int,
    on_progress: ProgressCallback | None = None,
) -> list[list[float]]:
    """Embed ``texts``, refusing anything that is not ``dimension`` wide."""
    vectors: list[list[float]] = []
    for start, batch in batch_texts(texts, batch_size=batch_size):
        produced = await client.embed(batch)
        if len(produced) != len(batch):
            raise EmbeddingError(
                f"embedding server returned {len(produced)} vectors for "
                f"{len(batch)} inputs"
            )
        for offset, vector in enumerate(produced):
            if len(vector) != dimension:
                raise EmbeddingError(
                    f"embedding {start + offset} has {len(vector)} dimensions, "
                    f"but the database column stores {dimension}; "
                    "set EMBEDDING_DIMENSION to the model's real size and "
                    "reindex"
                )
            vectors.append(vector)
        logger.debug("embedded chunks %d-%d", start, start + len(batch) - 1)
        if on_progress is not None:
            await on_progress(len(vectors), len(texts))
    return vectors
