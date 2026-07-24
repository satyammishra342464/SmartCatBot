"""Persistent local vector index: Gemini embeddings + numpy cosine search, with lexical fallback."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import numpy as np

EMBED_BATCH = 50


class VectorStore:
    def __init__(self, index_file: str | Path | None = None):
        """index_file=None gives a purely in-memory store (e.g. per-session uploads)."""
        self.index_file = Path(index_file) if index_file else None
        self.chunks: list[dict] = []
        self._matrix: np.ndarray | None = None
        if self.index_file and self.index_file.exists():
            self._load()

    # ------------------------------------------------------------------ indexing

    def add_document(self, doc_name: str, chunks: list[dict], client, embed_model: str) -> int:
        """Embed and index all chunks of one document, replacing any previous version."""
        self.remove_document(doc_name)
        if client is not None and chunks:
            texts = [c["text"] for c in chunks]
            vectors = _embed_texts(client, embed_model, texts, task="RETRIEVAL_DOCUMENT")
            for chunk, vec in zip(chunks, vectors):
                chunk["embedding"] = vec
        self.chunks.extend(chunks)
        self._matrix = None
        self._save()
        return len(chunks)

    def remove_document(self, doc_name: str) -> None:
        before = len(self.chunks)
        self.chunks = [c for c in self.chunks if c["doc"] != doc_name]
        if len(self.chunks) != before:
            self._matrix = None
            self._save()

    def clear(self) -> None:
        self.chunks = []
        self._matrix = None
        if self.index_file and self.index_file.exists():
            self.index_file.unlink()

    @property
    def documents(self) -> dict[str, int]:
        """Indexed document names -> chunk counts."""
        docs: dict[str, int] = {}
        for chunk in self.chunks:
            docs[chunk["doc"]] = docs.get(chunk["doc"], 0) + 1
        return docs

    # ------------------------------------------------------------------ retrieval

    def search(self, query: str, client, embed_model: str, top_k: int = 6) -> list[dict]:
        if not self.chunks:
            return []
        embedded = [c for c in self.chunks if "embedding" in c]
        if client is not None and embedded:
            return self._vector_search(query, embedded, client, embed_model, top_k)
        return self._lexical_search(query, top_k)

    def _vector_search(self, query, chunks, client, embed_model, top_k) -> list[dict]:
        query_vec = np.array(_embed_texts(client, embed_model, [query], task="RETRIEVAL_QUERY")[0])
        matrix = np.array([c["embedding"] for c in chunks])
        norms = np.linalg.norm(matrix, axis=1) * np.linalg.norm(query_vec)
        norms[norms == 0] = 1e-9
        scores = matrix @ query_vec / norms
        order = np.argsort(scores)[::-1][:top_k]
        return [{**chunks[i], "score": float(scores[i])} for i in order]

    def _lexical_search(self, query, top_k) -> list[dict]:
        query_tokens = set(_tokenize(query))
        scored = []
        for chunk in self.chunks:
            tokens = _tokenize(chunk["text"])
            if not tokens:
                continue
            overlap = len(query_tokens & set(tokens))
            if overlap:
                scored.append((overlap / (len(tokens) ** 0.5), chunk))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [{**chunk, "score": score} for score, chunk in scored[:top_k]]

    # ------------------------------------------------------------------ persistence

    def _save(self) -> None:
        if self.index_file is None:
            return
        self.index_file.parent.mkdir(parents=True, exist_ok=True)
        self.index_file.write_text(json.dumps({"chunks": self.chunks}), encoding="utf-8")

    def _load(self) -> None:
        data = json.loads(self.index_file.read_text(encoding="utf-8"))
        self.chunks = data.get("chunks", [])


def _embed_texts(client, model: str, texts: list[str], task: str) -> list[list[float]]:
    return _embed_uncached(client, model, texts, task)


def _embed_uncached(client, model: str, texts: list[str], task: str) -> list[list[float]]:
    from google.genai import types

    vectors: list[list[float]] = []
    for start in range(0, len(texts), EMBED_BATCH):
        batch = texts[start : start + EMBED_BATCH]
        # Each text must be its own Content object — a plain list of strings is
        # merged into ONE content by the SDK and returns a single embedding.
        response = client.models.embed_content(
            model=model,
            contents=[types.Content(parts=[types.Part.from_text(text=t)]) for t in batch],
            config=types.EmbedContentConfig(task_type=task),
        )
        if len(response.embeddings) != len(batch):
            raise RuntimeError(
                f"Embedding count mismatch: sent {len(batch)}, got {len(response.embeddings)}"
            )
        vectors.extend(list(e.values) for e in response.embeddings)
    return vectors


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())
