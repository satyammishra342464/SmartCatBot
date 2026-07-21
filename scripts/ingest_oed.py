#!/usr/bin/env python3
"""Download the OED (Open Exposure Data) spec CSVs from GitHub into the corpus.

Pulls the OasisLMF/ODS_OpenExposureData repo zip, extracts the relevant CSVs
(occupancy/construction/field specs) and writes corpus records so build_stores
puts every row into the code DB (exact lookups) with a lean text for the
vector index.
"""
from __future__ import annotations

import csv
import io
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import core  # noqa: F401 — activates truststore for the corporate proxy
import requests

REPO_ZIP = "https://codeload.github.com/OasisLMF/ODS_OpenExposureData/zip/refs/heads/main"
REPO_WEB = "https://github.com/OasisLMF/ODS_OpenExposureData"
CORPUS_DIR = ROOT / "data" / "corpus"
KEYWORDS = ("occupancy", "construction", "oedinputfields", "peril", "currency")
MAX_PREVIEW_ROWS = 30


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def main() -> None:
    print(f"Downloading {REPO_ZIP} ...", flush=True)
    response = requests.get(REPO_ZIP, timeout=120)
    response.raise_for_status()
    archive = zipfile.ZipFile(io.BytesIO(response.content))

    written = 0
    for member in archive.namelist():
        base = Path(member).name.lower()
        if not base.endswith(".csv") or not any(kw in base for kw in KEYWORDS):
            continue
        raw = archive.read(member).decode("utf-8-sig", errors="ignore")
        rows = list(csv.reader(io.StringIO(raw)))
        if len(rows) < 2:
            continue
        headers, data_rows = rows[0], [r for r in rows[1:] if any(cell.strip() for cell in r)]

        preview = "\n".join(
            "| " + " | ".join(row) + " |" for row in data_rows[:MAX_PREVIEW_ROWS]
        )
        record = {
            "url": f"{REPO_WEB}/blob/main/{member.split('/', 1)[-1]}",
            "title": f"OED spec — {Path(member).name}",
            "section": "oed",
            "version": None,
            "text": (
                f"OED (Open Exposure Data) specification file {Path(member).name} from Oasis LMF "
                f"Open Data Standards. Columns: {', '.join(headers)}. {len(data_rows)} rows. "
                f"Sample rows:\n| {' | '.join(headers)} |\n{preview}"
            ),
            "tables": [{"headers": headers, "rows": data_rows}],
        }
        out_file = CORPUS_DIR / f"oed__{_slug(Path(member).stem)}.json"
        out_file.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
        written += 1
        print(f"  {Path(member).name}: {len(data_rows)} rows")

    if not written:
        sys.exit("No matching CSVs found in the OED repo — check KEYWORDS or repo layout.")
    print(f"Done: {written} OED spec files ingested. Now run: python scripts/build_stores.py")


if __name__ == "__main__":
    main()
