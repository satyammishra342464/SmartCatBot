"""GeoNames postal-code lookups stored in SQLite (table: postal_codes)."""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

GEONAMES_URL = "https://www.geonames.org/"


class GeoDB:
    def __init__(self, db_file: str | Path):
        self.db_file = str(db_file)

    @property
    def available(self) -> bool:
        if not Path(self.db_file).exists():
            return False
        con = sqlite3.connect(self.db_file)
        try:
            row = con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='postal_codes'"
            ).fetchone()
            return row is not None
        finally:
            con.close()

    def build(self, rows) -> int:
        """rows: iterable of (country, postal, place, admin1, admin2, lat, lng)."""
        Path(self.db_file).parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.db_file)
        con.executescript(
            """
            DROP TABLE IF EXISTS postal_codes;
            CREATE TABLE postal_codes (
                country TEXT, postal TEXT, place TEXT,
                admin1 TEXT, admin2 TEXT, lat REAL, lng REAL
            );
            """
        )
        count = 0
        batch = []
        for row in rows:
            batch.append(row)
            if len(batch) >= 20000:
                con.executemany("INSERT INTO postal_codes VALUES (?,?,?,?,?,?,?)", batch)
                count += len(batch)
                batch = []
        if batch:
            con.executemany("INSERT INTO postal_codes VALUES (?,?,?,?,?,?,?)", batch)
            count += len(batch)
        con.execute("CREATE INDEX idx_postal ON postal_codes(postal)")
        con.execute("CREATE INDEX idx_place ON postal_codes(place COLLATE NOCASE)")
        con.commit()
        con.close()
        return count

    def search(self, query: str, top_k: int = 10) -> list[dict]:
        if not self.available:
            return [{"error": "postal database not built — run scripts/ingest_geonames.py"}]
        con = sqlite3.connect(self.db_file)
        con.row_factory = sqlite3.Row
        try:
            code_match = re.search(r"\b([A-Za-z0-9][A-Za-z0-9 -]{2,9})\b", query)
            rows = []
            digits = re.search(r"\b(\d{4,6})\b", query)
            if digits:
                rows = con.execute(
                    "SELECT * FROM postal_codes WHERE postal LIKE ? LIMIT ?",
                    (digits.group(1) + "%", top_k),
                ).fetchall()
            if not rows:
                place = re.sub(r"\b(pincode|pin|postal|zip|code|of|the|what|is)\b", " ",
                               query, flags=re.I).strip()
                if place:
                    rows = con.execute(
                        "SELECT * FROM postal_codes WHERE place LIKE ? COLLATE NOCASE LIMIT ?",
                        ("%" + place + "%", top_k),
                    ).fetchall()
            results = []
            for row in rows:
                results.append({
                    "title": "GeoNames postal database",
                    "url": GEONAMES_URL,
                    "entry": (f"{row['country']} {row['postal']} — {row['place']}, "
                              f"{row['admin1'] or ''} {row['admin2'] or ''}"
                              f" (lat {row['lat']}, lng {row['lng']})").strip(),
                })
            return results
        finally:
            con.close()
