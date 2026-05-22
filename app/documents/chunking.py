from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    index: int
    text: str
    start_char: int
    end_char: int


def chunk_text(text: str, chunk_size: int = 900, overlap: int = 150) -> list[TextChunk]:
    cleaned = " ".join(text.split())
    if not cleaned:
        return []
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")
    if overlap < 0:
        raise ValueError("overlap cannot be negative")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    chunks: list[TextChunk] = []
    start = 0
    while start < len(cleaned):
        end = min(start + chunk_size, len(cleaned))
        chunks.append(
            TextChunk(
                index=len(chunks),
                text=cleaned[start:end],
                start_char=start,
                end_char=end,
            )
        )
        if end == len(cleaned):
            break
        start = end - overlap
    return chunks
