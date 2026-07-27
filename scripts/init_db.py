#!/usr/bin/env python3
"""Create all Postgres tables. Idempotent — safe to re-run.

Usage: python scripts/init_db.py  (requires DATABASE_URL in .env)"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from db.engine import active_db_url, init_db  # noqa: E402


def main() -> None:
    init_db()
    url = active_db_url()
    safe = url.split("@")[-1] if "@" in url else url
    print(f"Tables created on {safe}")
    print("Done.")


if __name__ == "__main__":
    main()
