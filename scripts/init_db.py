#!/usr/bin/env python3
"""Create all Postgres tables. Idempotent — safe to re-run.

Usage: python scripts/init_db.py  (requires DATABASE_URL in .env)"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from db.engine import get_settings, init_db  # noqa: E402


def main() -> None:
    url = get_settings().database_url
    # hide credentials when echoing
    safe = url.split("@")[-1] if "@" in url else url
    print(f"Creating tables on {safe} ...")
    init_db()
    print("Done.")


if __name__ == "__main__":
    main()
