"""Corpus vector index: Gemini embeddings (.npy) + JSON chunk metadata.

Search is hybrid: cosine similarity (semantic) fused with lexical token-overlap
scores via Reciprocal Rank Fusion, so exact terms like field names (UNDCOVAMT)
rank well alongside conceptual matches.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np

from core.vector_store import _embed_texts

EMBED_BATCH = 50
RRF_K = 60
CANDIDATES = 50


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


class KnowledgeIndex:
    def __init__(self, index_dir: str | Path):
        self.index_dir = Path(index_dir)
        self.meta_file = self.index_dir / "chunks.json"
        self.vec_file = self.index_dir / "embeddings.npy"
        self.chunks: list[dict] = []
        self.matrix: np.ndarray | None = None
        self._token_sets: list[set[str]] = []

    @property
    def exists(self) -> bool:
        return self.meta_file.exists() and self.vec_file.exists()

    def load(self) -> "KnowledgeIndex":
        self.chunks = json.loads(self.meta_file.read_text(encoding="utf-8"))
        self.matrix = np.load(self.vec_file)
        self._token_sets = [_tokenize(c["text"]) for c in self.chunks]
        return self

    def build(self, chunk_records: list[dict], client, embed_model: str, log=print) -> int:
        """chunk_records: [{text, url, title, section, version}] — embeds and persists."""
        texts = [c["text"] for c in chunk_records]
        vectors: list[list[float]] = []
        for start in range(0, len(texts), EMBED_BATCH):
            batch = texts[start : start + EMBED_BATCH]
            vectors.extend(_embed_texts(client, embed_model, batch, task="RETRIEVAL_DOCUMENT"))
            if (start // EMBED_BATCH) % 10 == 0:
                log(f"  embedded {start + len(batch)}/{len(texts)} chunks")
        if len(vectors) != len(chunk_records):
            raise RuntimeError(
                f"Vector/chunk mismatch: {len(vectors)} vectors for {len(chunk_records)} chunks"
            )
        self.chunks = chunk_records
        self.matrix = np.array(vectors, dtype=np.float32)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.meta_file.write_text(json.dumps(chunk_records, ensure_ascii=False), encoding="utf-8")
        np.save(self.vec_file, self.matrix)
        return len(chunk_records)

    def search(self, query: str, client, embed_model: str, top_k: int = 10) -> list[dict]:
        """Hybrid search: vector cosine + lexical overlap, fused with RRF."""
        if self.matrix is None or not len(self.chunks):
            return []
        query_vec = np.array(
            _embed_texts(client, embed_model, [query], task="RETRIEVAL_QUERY")[0],
            dtype=np.float32,
        )
        denom = np.linalg.norm(self.matrix, axis=1) * np.linalg.norm(query_vec)
        denom = np.where(denom == 0, 1e-9, denom)
        cosine = self.matrix @ query_vec / denom
        vector_order = np.argsort(cosine)[::-1][:CANDIDATES]

        query_tokens = _tokenize(query)
        lexical = [
            (len(query_tokens & tokens) / (len(tokens) ** 0.5 + 1), i)
            for i, tokens in enumerate(self._token_sets)
        ]
        lexical_order = [i for score, i in sorted(lexical, reverse=True)[:CANDIDATES] if score > 0]

        fused: dict[int, float] = {}
        for rank, idx in enumerate(vector_order):
            fused[int(idx)] = fused.get(int(idx), 0.0) + 1.0 / (RRF_K + rank)
        for rank, idx in enumerate(lexical_order):
            fused[idx] = fused.get(idx, 0.0) + 1.0 / (RRF_K + rank)

        top = sorted(fused, key=fused.get, reverse=True)[:top_k]
        return [{**self.chunks[i], "score": fused[i]} for i in top]
