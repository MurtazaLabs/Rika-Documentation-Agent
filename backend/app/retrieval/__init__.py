"""Hybrid retrieval over indexed document chunks.

The package is deliberately split along the retrieval stages:

- ``vector_search`` queries pgvector for semantic neighbours.
- ``keyword_search`` queries PostgreSQL full-text search for exact terms.
- ``filters`` builds the project-scoped metadata predicate used by both.
- ``hybrid`` fuses the two ranked lists with Reciprocal Rank Fusion.
- ``evaluation`` holds the metric helpers used by the offline baseline.
"""

from __future__ import annotations

from app.retrieval.hybrid import reciprocal_rank_fusion, rank_hits
from app.retrieval.types import ChunkCandidate, RetrievedChunk, SearchFilters

__all__ = [
    "ChunkCandidate",
    "RetrievedChunk",
    "SearchFilters",
    "rank_hits",
    "reciprocal_rank_fusion",
]
