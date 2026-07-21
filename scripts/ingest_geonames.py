#!/usr/bin/env python3
"""Download the GeoNames worldwide postal-code dataset and load it into SQLite.

Usage:
  python scripts/ingest_geonames.py                 # all countries (~1.7M rows)
  python scripts/ingest_geonames.py --countries IN,US,AU,GB
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import core  # noqa: F401 — activates truststore for the corporate proxy
import requests

from core.geo_db import GeoDB

DOWNLOAD_URL = "https://download.geonames.org/export/zip/allCountries.zip"
DOWNLOADS_DIR = ROOT / "data" / "downloads"
DB_FILE = ROOT / "data" / "index" / "codes.db"


def main() -> None:
    ap = argparse.ArgumentParser(description="Load GeoNames postal codes into SQLite")
    ap.add_argument("--countries", default=None,
                    help="Comma-separated ISO2 codes to keep (default: all)")
    args = ap.parse_args()
    keep = {c.strip().upper() for c in args.countries.split(",")} if args.countries else None

    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = DOWNLOADS_DIR / "geonames_allCountries.zip"
    if not zip_path.exists():
        print(f"Downloading {DOWNLOAD_URL} ...", flush=True)
        with requests.get(DOWNLOAD_URL, stream=True, timeout=120) as response:
            response.raise_for_status()
            with open(zip_path, "wb") as fh:
                for chunk in response.iter_content(chunk_size=1 << 20):
                    fh.write(chunk)
        print(f"Downloaded {zip_path.stat().st_size / 1e6:.1f} MB")
    else:
        print(f"Using cached {zip_path}")

    def rows():
        with zipfile.ZipFile(zip_path) as zf:
            with zf.open("allCountries.txt") as fh:
                reader = csv.reader(io.TextIOWrapper(fh, encoding="utf-8"), delimiter="\t")
                for record in reader:
                    # GeoNames postal format: country, postal, place, admin1, code1, admin2, ...
                    if len(record) < 11:
                        continue
                    country = record[0]
                    if keep and country not in keep:
                        continue
                    lat = float(record[9]) if record[9] else None
                    lng = float(record[10]) if record[10] else None
                    yield (country, record[1], record[2], record[3], record[5], lat, lng)

    print("Loading into SQLite (postal_codes table)...", flush=True)
    count = GeoDB(DB_FILE).build(rows())
    print(f"Done: {count:,} postal codes -> {DB_FILE}")


if __name__ == "__main__":
    main()
