"""SQLite FTS5 store for exact code lookups over tables parsed from UNICEDE pages."""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path


class CodeDB:
    def __init__(self, db_file: str | Path):
        self.db_file = str(db_file)

    @property
    def exists(self) -> bool:
        return Path(self.db_file).exists()

    def build(self, records: list[dict]) -> int:
        """records: parsed corpus pages with a `tables` list. Rebuilds the DB from scratch."""
        Path(self.db_file).parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.db_file)
        con.executescript(
            """
            DROP TABLE IF EXISTS code_rows;
            DROP TABLE IF EXISTS code_rows_fts;
            CREATE TABLE code_rows (
                id INTEGER PRIMARY KEY,
                url TEXT, title TEXT, section TEXT, version TEXT,
                headers TEXT, row TEXT, row_text TEXT
            );
            CREATE VIRTUAL TABLE code_rows_fts USING fts5(
                row_text, title, content='code_rows', content_rowid='id'
            );
            """
        )
        inserted = 0
        for record in records:
            for table in record.get("tables", []):
                headers = table.get("headers", [])
                for row in table.get("rows", []):
                    row_text = " | ".join(cell for cell in row if cell)
                    if not row_text:
                        continue
                    con.execute(
                        "INSERT INTO code_rows (url, title, section, version, headers, row, row_text) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            record["url"], record["title"], record["section"],
                            record["version"], json.dumps(headers), json.dumps(row), row_text,
                        ),
                    )
                    inserted += 1
        con.execute("INSERT INTO code_rows_fts(rowid, row_text, title) SELECT id, row_text, title FROM code_rows")
        con.commit()
        con.close()
        return inserted

    def search(self, query: str, top_k: int = 12) -> list[dict]:
        tokens = re.findall(r"[A-Za-z0-9]+", query)
        if not tokens or not self.exists:
            return []
        match = " OR ".join(f'"{t}"' for t in tokens)
        con = sqlite3.connect(self.db_file)
        con.row_factory = sqlite3.Row
        try:
            rows = con.execute(
                """
                SELECT c.url, c.title, c.version, c.headers, c.row, bm25(code_rows_fts) AS rank
                FROM code_rows_fts f JOIN code_rows c ON c.id = f.rowid
                WHERE code_rows_fts MATCH ? ORDER BY rank LIMIT ?
                """,
                (match, top_k),
            ).fetchall()
        finally:
            con.close()
        results = []
        for row in rows:
            headers = json.loads(row["headers"])
            values = json.loads(row["row"])
            if headers and len(headers) == len(values):
                entry = "; ".join(f"{h}: {v}" for h, v in zip(headers, values) if v)
            else:
                entry = " | ".join(v for v in values if v)
            results.append({
                "title": row["title"],
                "url": row["url"],
                "version": row["version"],
                "entry": entry,
            })
        return results

    def count_rows(self) -> int:
        if not self.exists:
            return 0
        con = sqlite3.connect(self.db_file)
        try:
            return con.execute("SELECT COUNT(*) FROM code_rows").fetchone()[0]
        finally:
            con.close()
