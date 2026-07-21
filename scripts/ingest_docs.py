#!/usr/bin/env python3
"""Ingest local documents (PDF/DOCX/TXT/MD/CSV) into the corpus as page-level records.

Drop files into data/local_docs/ then run:
  python scripts/ingest_docs.py
  python scripts/build_stores.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.loader import SUPPORTED_EXTENSIONS, load_document

LOCAL_DIR = ROOT / "data" / "local_docs"
CORPUS_DIR = ROOT / "data" / "corpus"
MIN_TEXT_CHARS = 40


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _load_xlsx(path: Path) -> tuple[list[dict], list[dict]]:
    """Returns (blocks, tables) — one block+table per sheet."""
    import openpyxl

    workbook = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    blocks, tables = [], []
    for sheet in workbook.worksheets:
        rows = [[("" if c is None else str(c).strip()) for c in row]
                for row in sheet.iter_rows(values_only=True)]
        rows = [r for r in rows if any(r)]
        if len(rows) < 2:
            continue
        headers, data_rows = rows[0], rows[1:]
        markdown = "\n".join("| " + " | ".join(r) + " |" for r in [headers] + data_rows[:50])
        blocks.append({"page": None, "sheet": sheet.title,
                       "text": f"Sheet '{sheet.title}' ({len(data_rows)} rows):\n{markdown}"})
        tables.append({"headers": headers, "rows": data_rows})
    return blocks, tables


def main() -> None:
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    extensions = SUPPORTED_EXTENSIONS + (".xlsx",)
    files = [p for p in LOCAL_DIR.iterdir() if p.suffix.lower() in extensions]
    if not files:
        sys.exit(f"No documents found in {LOCAL_DIR} — drop PDF/DOCX/TXT/XLSX files there first.")

    total = 0
    skipped = 0
    for path in files:
        if path.suffix.lower() == ".xlsx":
            blocks, xlsx_tables = _load_xlsx(path)
            for i, (block, table) in enumerate(zip(blocks, xlsx_tables)):
                record = {
                    "url": path.resolve().as_uri(),
                    "title": f"{path.name} — sheet {block['sheet']}",
                    "section": "local-docs",
                    "version": None,
                    "text": block["text"],
                    "tables": [table],
                }
                out_file = CORPUS_DIR / f"local__{_slug(path.stem)}__s{i:02d}.json"
                out_file.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
                total += 1
            print(f"{path.name}: {len(blocks)} sheets -> {total} records so far")
            continue
        blocks = load_document(path)
        for block in blocks:
            if len(block["text"]) < MIN_TEXT_CHARS:
                skipped += 1
                continue
            page = block["page"]
            record = {
                "url": path.resolve().as_uri(),
                "title": path.name if page is None else f"{path.name} — page {page}",
                "section": "local-docs",
                "version": None,
                "text": block["text"],
                "tables": [],
            }
            suffix = f"p{page:03d}" if page else "doc"
            out_file = CORPUS_DIR / f"local__{_slug(path.stem)}__{suffix}.json"
            out_file.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
            total += 1
        print(f"{path.name}: {len(blocks)} pages -> {total} records so far")

    print(f"Done: {total} records ingested ({skipped} near-empty pages skipped)")
    print("Now rebuild the stores: python scripts/build_stores.py")


if __name__ == "__main__":
    main()
