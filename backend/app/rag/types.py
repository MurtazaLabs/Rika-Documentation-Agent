"""Types shared by prompt assembly and citation validation."""

from __future__ import annotations

from dataclasses import dataclass

from app.retrieval.types import RetrievedChunk


@dataclass(frozen=True, slots=True)
class PromptSource:
    """A retrieved chunk that was actually included in the prompt.

    The marker (``S1``, ``S2``, ...) is assigned only to sources that fit the
    context budget, so generated citations always resolve to a source the
    model really saw.
    """

    marker: str
    hit: RetrievedChunk


@dataclass(frozen=True, slots=True)
class HistoryTurn:
    """One prior user or assistant message, already stripped for prompting."""

    role: str
    content: str

