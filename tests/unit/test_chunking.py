import pytest

from app.documents.chunking import chunk_text


def test_chunk_text_returns_overlapping_chunks() -> None:
    chunks = chunk_text("a" * 25, chunk_size=10, overlap=2)

    assert len(chunks) == 3
    assert chunks[0].text == "a" * 10
    assert chunks[1].start_char == 8
    assert chunks[2].end_char == 25


def test_chunk_text_rejects_invalid_overlap() -> None:
    with pytest.raises(ValueError, match="overlap must be smaller"):
        chunk_text("hello", chunk_size=10, overlap=10)
