"""Reciprocal Rank Fusion and single-signal ranking.

RRF combines two ranked lists without comparing their raw scores (a cosine
similarity and a ``ts_rank_cd`` value are not on the same scale):

``score = sum(1 / (k + rank))``

``k`` is the usual 60, which keeps the top of each list influential without
letting one signal dominate. Chunks are deduplicated by id, so a result found
by both signals appears once with both component scores.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.retrieval.types import ChunkCandidate, RetrievedChunk

RRF_K = 60


@dataclass(slots=True)
class _Merged:
    candidate: ChunkCandidate
    score: float = 0.0
    vector_score: float | None = None
    keyword_score: float | None = None
    vector_rank: int | None = None
    keyword_rank: int | None = None
    matched_by: list[str] = field(default_factory=list)

    @property
    def best_rank(self) -> int:
        ranks = [
            rank
            for rank in (self.vector_rank, self.keyword_rank)
            if rank is not None
        ]
        return min(ranks) if ranks else 0


def reciprocal_rank_fusion(
    vector_hits: list[ChunkCandidate],
    keyword_hits: list[ChunkCandidate],
    *,
    limit: int,
    k: int = RRF_K,
) -> list[RetrievedChunk]:
    """Fuse two ranked lists, deduplicate by chunk id and cut to ``limit``."""
    merged: dict[object, _Merged] = {}

    for rank, hit in enumerate(vector_hits, start=1):
        entry = merged.get(hit.chunk.id)
        if entry is not None and entry.vector_rank is not None:
            continue
        if entry is None:
            entry = _Merged(candidate=hit)
            merged[hit.chunk.id] = entry
        entry.vector_score = hit.vector_score
        entry.vector_rank = rank
        entry.score += 1.0 / (k + rank)
        entry.matched_by.append("vector")

    for rank, hit in enumerate(keyword_hits, start=1):
        entry = merged.get(hit.chunk.id)
        if entry is not None and entry.keyword_rank is not None:
            continue
        if entry is None:
            entry = _Merged(candidate=hit)
            merged[hit.chunk.id] = entry
        entry.keyword_score = hit.keyword_score
        entry.keyword_rank = rank
        entry.score += 1.0 / (k + rank)
        entry.matched_by.append("keyword")

    ordered = sorted(
        merged.values(),
        key=lambda entry: (
            -entry.score,
            entry.best_rank,
            entry.candidate.chunk.chunk_index,
            str(entry.candidate.chunk.id),
        ),
    )
    return [
        RetrievedChunk(
            chunk=entry.candidate.chunk,
            file_path=entry.candidate.file_path,
            filename=entry.candidate.filename,
            file_type=entry.candidate.file_type,
            rank=rank,
            score=entry.score,
            vector_score=entry.vector_score,
            keyword_score=entry.keyword_score,
            matched_by=tuple(entry.matched_by),
        )
        for rank, entry in enumerate(ordered[:limit], start=1)
    ]


def rank_hits(
    hits: list[ChunkCandidate], *, source: str, limit: int
) -> list[RetrievedChunk]:
    """Rank one signal's hits without fusion (used by ``mode=vector|keyword``)."""
    seen: set[object] = set()
    results: list[RetrievedChunk] = []
    for hit in hits:
        if hit.chunk.id in seen:
            continue
        seen.add(hit.chunk.id)
        score = (
            hit.vector_score
            if source == "vector"
            else hit.keyword_score
        )
        results.append(
            RetrievedChunk(
                chunk=hit.chunk,
                file_path=hit.file_path,
                filename=hit.filename,
                file_type=hit.file_type,
                rank=len(results) + 1,
                score=float(score or 0.0),
                vector_score=hit.vector_score,
                keyword_score=hit.keyword_score,
                matched_by=(source,),
            )
        )
        if len(results) >= limit:
            break
    return results
