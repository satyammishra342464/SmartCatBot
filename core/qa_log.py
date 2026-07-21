"""Question/answer logging + user feedback, stored in SQLite."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path


class QALog:
    def __init__(self, db_file: str | Path):
        self.db_file = str(db_file)
        Path(self.db_file).parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.db_file)
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS qa_log (
                id INTEGER PRIMARY KEY,
                ts REAL,
                question TEXT,
                answer TEXT,
                tool_calls TEXT,
                sources TEXT,
                kb_hit INTEGER,
                feedback INTEGER DEFAULT 0
            )
            """
        )
        con.commit()
        con.close()

    def log(self, question: str, answer: str, tool_calls: list, sources: list) -> int:
        kb_hit = 1 if any(c.get("hits", 0) > 0 for c in tool_calls) else 0
        con = sqlite3.connect(self.db_file)
        try:
            cursor = con.execute(
                "INSERT INTO qa_log (ts, question, answer, tool_calls, sources, kb_hit) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (time.time(), question, answer,
                 json.dumps(tool_calls, ensure_ascii=False),
                 json.dumps(sources, ensure_ascii=False), kb_hit),
            )
            con.commit()
            return int(cursor.lastrowid)
        finally:
            con.close()

    def set_feedback(self, log_id: int, feedback: int) -> None:
        con = sqlite3.connect(self.db_file)
        try:
            con.execute("UPDATE qa_log SET feedback = ? WHERE id = ?", (feedback, log_id))
            con.commit()
        finally:
            con.close()

    def stats(self) -> dict:
        con = sqlite3.connect(self.db_file)
        try:
            total, up, down = con.execute(
                "SELECT COUNT(*), SUM(feedback = 1), SUM(feedback = -1) FROM qa_log"
            ).fetchone()
            return {"total": total or 0, "up": up or 0, "down": down or 0}
        finally:
            con.close()
