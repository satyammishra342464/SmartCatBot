#!/usr/bin/env python3
"""Phase 2: build both knowledge stores from the crawled corpus.

- Vector index (Gemini embeddings + numpy) for semantic search
- SQLite FTS5 code DB for exact code lookups

Keeps only the latest version of versioned pages (e.g. _2-10 wins over _2-9).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

from core.chunker import chunk_text
from core.code_db import CodeDB
from core.knowledge_index import KnowledgeIndex
from core.parser import VERSION_RE

load_dotenv(ROOT / ".env")

CORPUS_DIR = ROOT / "data" / "corpus"
INDEX_DIR = ROOT / "data" / "index"
DB_FILE = INDEX_DIR / "codes.db"


def _version_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def _family(url: str) -> str:
    stem = url.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    return VERSION_RE.sub("", stem)


def filter_latest(records: list[dict]) -> list[dict]:
    latest: dict[str, tuple[int, ...]] = {}
    for record in records:
        if record["version"]:
            family = _family(record["url"])
            candidate = _version_tuple(record["version"])
            if family not in latest or candidate > latest[family]:
                latest[family] = candidate
    kept = []
    for record in records:
        if not record["version"]:
            kept.append(record)
        elif _version_tuple(record["version"]) == latest[_family(record["url"])]:
            kept.append(record)
    return kept


def main() -> None:
    ap = argparse.ArgumentParser(description="Build vector index + code DB from corpus")
    ap.add_argument("--skip-embeddings", action="store_true", help="Only build the SQLite code DB")
    args = ap.parse_args()

    records = []
    for path in sorted(CORPUS_DIR.glob("*.json")):
        records.append(json.loads(path.read_text(encoding="utf-8")))
    if not records:
        sys.exit(f"No corpus files in {CORPUS_DIR} — run scripts/crawl_unicede.py first.")

    kept = filter_latest(records)
    print(f"Corpus: {len(records)} pages, {len(kept)} after latest-version filter")

    db = CodeDB(DB_FILE)
    row_count = db.build(kept)
    print(f"Code DB: {row_count} table rows -> {DB_FILE}")

    if args.skip_embeddings:
        return

    import os
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        sys.exit("GEMINI_API_KEY missing in .env — cannot build embeddings.")
    from google import genai

    client = genai.Client(api_key=api_key)
    embed_model = os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-2")

    chunk_records = []
    for record in kept:
        for piece in chunk_text(record["text"]):
            chunk_records.append({
                "text": f"{record['title']}\n{piece}",
                "url": record["url"],
                "title": record["title"],
                "section": record["section"],
                "version": record["version"],
            })
    print(f"Embedding {len(chunk_records)} chunks with {embed_model} ...")
    index = KnowledgeIndex(INDEX_DIR)
    total = index.build(chunk_records, client, embed_model)
    print(f"Vector index: {total} chunks -> {INDEX_DIR}")


if __name__ == "__main__":
    main()
