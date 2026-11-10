"""Chunker behaviour: line ranges, overlap and overlong lines."""

from __future__ import annotations

from app.ingestion.chunking import chunk_text


def test_short_text_is_one_chunk() -> None:
    drafts = chunk_text("hello\nworld", max_chars=100, overlap_chars=10)
    assert len(drafts) == 1
    assert drafts[0].index == 0
    assert drafts[0].text == "hello\nworld"
    assert (drafts[0].start_line, drafts[0].end_line) == (1, 2)


def test_chunks_respect_the_size_limit() -> None:
    text = "\n".join(f"line {number:03d} padded out with text" for number in range(1, 41))
    drafts = chunk_text(text, max_chars=120, overlap_chars=30)
    assert len(drafts) > 1
    assert all(len(draft.text) <= 120 for draft in drafts)


def test_chunks_overlap_and_cover_every_line() -> None:
    lines = [f"line {number}" for number in range(1, 61)]
    drafts = chunk_text("\n".join(lines), max_chars=100, overlap_chars=25)

    assert drafts[0].start_line == 1
    assert drafts[-1].end_line == 60
    # Consecutive chunks overlap rather than leaving gaps.
    for previous, current in zip(drafts, drafts[1:]):
        assert current.start_line <= previous.end_line
    covered = {line for draft in drafts for line in range(draft.start_line, draft.end_line + 1)}
    assert covered == set(range(1, 61))


def test_long_single_line_is_split_and_keeps_its_line_number() -> None:
    drafts = chunk_text("x" * 250, max_chars=100, overlap_chars=20)
    assert len(drafts) >= 3
    assert {draft.start_line for draft in drafts} == {1}
    assert all(len(draft.text) <= 100 for draft in drafts)


def test_blank_text_returns_nothing() -> None:
    assert chunk_text("   \n\n\t\n", max_chars=100) == []
    assert chunk_text("", max_chars=100) == []
