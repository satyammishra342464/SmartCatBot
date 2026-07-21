#!/usr/bin/env python3
"""Phase 1: crawl the UNICEDE site and build the RAG-ready corpus.

Usage:
  python scripts/crawl_unicede.py --max-pages 12   # quick test
  python scripts/crawl_unicede.py                  # full crawl (resumable)
  python scripts/crawl_unicede.py --parse-only     # re-parse existing HTML
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.crawler import BASE_URL, MANIFEST_FILE, crawl
from core.parser import parse_page

RAW_DIR = ROOT / "data" / "raw_html"
CORPUS_DIR = ROOT / "data" / "corpus"
MIN_TEXT_CHARS = 40


def main() -> None:
    ap = argparse.ArgumentParser(description="Crawl UNICEDE and build corpus")
    ap.add_argument("--max-pages", type=int, default=None, help="Stop after N pages (testing)")
    ap.add_argument("--delay", type=float, default=0.4, help="Seconds between requests")
    ap.add_argument("--parse-only", action="store_true", help="Skip crawl, re-parse existing HTML")
    args = ap.parse_args()

    if not args.parse_only:
        print(f"Crawling {BASE_URL} (delay={args.delay}s, max={args.max_pages or 'all'})", flush=True)
        crawl(RAW_DIR, delay=args.delay, max_pages=args.max_pages,
              log=lambda msg: print(msg, flush=True))

    manifest_path = RAW_DIR / MANIFEST_FILE
    if not manifest_path.exists():
        sys.exit("No crawl manifest found — run without --parse-only first.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    pages = 0
    tables = 0
    skipped = 0
    for url, filename in manifest.items():
        html_path = RAW_DIR / filename
        if not html_path.exists():
            continue
        record = parse_page(html_path.read_text(encoding="utf-8", errors="ignore"), url)
        if len(record["text"]) < MIN_TEXT_CHARS:
            skipped += 1
            continue
        out_file = CORPUS_DIR / (filename.rsplit(".", 1)[0] + ".json")
        out_file.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
        pages += 1
        tables += len(record["tables"])

    print(f"Corpus built: {pages} pages, {tables} tables ({skipped} near-empty pages skipped)")
    print(f"Output: {CORPUS_DIR}")


if __name__ == "__main__":
    main()
