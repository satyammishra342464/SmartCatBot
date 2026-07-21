"""Split document text into overlapping word-window chunks for embedding."""
from __future__ import annotations

MAX_WORDS = 300
OVERLAP_WORDS = 50


def chunk_blocks(blocks: list[dict], doc_name: str) -> list[dict]:
    """Turn loader blocks into chunks: {"doc", "page", "text"}. Page info is kept for citations."""
    chunks: list[dict] = []
    for block in blocks:
        for piece in _split_words(block["text"]):
            chunks.append({"doc": doc_name, "page": block["page"], "text": piece})
    return chunks


def chunk_text(text: str, max_words: int = MAX_WORDS, overlap: int = OVERLAP_WORDS) -> list[str]:
    """Generic overlapping word-window chunking for any plain text."""
    return _split_words(text, max_words, overlap)


def _split_words(text: str, max_words: int = MAX_WORDS, overlap: int = OVERLAP_WORDS) -> list[str]:
    words = text.split()
    if not words:
        return []
    if len(words) <= max_words:
        return [" ".join(words)]
    pieces = []
    step = max_words - overlap
    for start in range(0, len(words), step):
        pieces.append(" ".join(words[start : start + max_words]))
        if start + max_words >= len(words):
            break
    return pieces
