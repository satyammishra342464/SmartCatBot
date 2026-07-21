#!/usr/bin/env python3
"""Auto-refresh: re-crawl UNICEDE only when its "What's new" pages change.

Run manually or on a schedule (see README). Flow:
  1. Fetch the What's-new pages and hash them.
  2. If the hash matches the stored one -> up to date, exit.
  3. Otherwise: clear raw HTML, full re-crawl, re-parse, rebuild both stores.

Use --force to skip the check and refresh unconditionally.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import core  # noqa: F401 — activates truststore
import requests

WHATS_NEW_URLS = [
    "https://unicede.air-worldwide.com/unicede/unicede_whats-new.html",
    "https://unicede.air-worldwide.com/ts_val-ref_intro/ts_val-ref_intro_whats-new-2025-13-1.html",
]
STATE_FILE = ROOT / "data" / "refresh_state.json"
RAW_DIR = ROOT / "data" / "raw_html"
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"


def current_hash() -> str:
    digest = hashlib.sha256()
    for url in WHATS_NEW_URLS:
        try:
            response = requests.get(url, timeout=30)
            digest.update(response.content)
        except requests.RequestException as exc:
            print(f"WARN: could not fetch {url}: {exc}")
    return digest.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser(description="Refresh UNICEDE corpus if the site changed")
    ap.add_argument("--force", action="store_true", help="Refresh even if unchanged")
    args = ap.parse_args()

    new_hash = current_hash()
    old_hash = None
    if STATE_FILE.exists():
        old_hash = json.loads(STATE_FILE.read_text(encoding="utf-8")).get("whats_new_hash")

    if not args.force and old_hash == new_hash:
        print("UNICEDE unchanged — corpus is up to date.")
        return

    print("Change detected (or --force) — refreshing corpus...")
    if RAW_DIR.exists():
        shutil.rmtree(RAW_DIR)
        print("Cleared cached HTML.")

    subprocess.run([str(PYTHON), str(ROOT / "scripts" / "crawl_unicede.py")], check=True)
    subprocess.run([str(PYTHON), str(ROOT / "scripts" / "build_stores.py")], check=True)

    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({"whats_new_hash": new_hash}), encoding="utf-8")
    print("Refresh complete.")


if __name__ == "__main__":
    main()
