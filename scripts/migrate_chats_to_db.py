#!/usr/bin/env python3
"""One-time import of existing data/chats.json + data/index/qa_log.db into Postgres,
attributed to SMARTCAT_USER_EMAIL, so no history is lost when moving off the JSON file.

Usage: python scripts/migrate_chats_to_db.py  (run after scripts/init_db.py)"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import text  # noqa: E402

from db.engine import init_db, session_scope  # noqa: E402
from db.models import QALogRow  # noqa: E402
from db.repositories import ChatRepo, UserRepo  # noqa: E402
from service.config import get_settings  # noqa: E402

CHATS_FILE = ROOT / "data" / "chats.json"
QALOG_DB = ROOT / "data" / "index" / "qa_log.db"


def _migrate_chats(user_id: str) -> int:
    if not CHATS_FILE.exists():
        print("no chats.json — skipping chats")
        return 0
    chats = json.loads(CHATS_FILE.read_text(encoding="utf-8"))
    repo = ChatRepo()
    for chat in chats:
        repo.save(user_id, chat)
    print(f"imported {len(chats)} chats")
    return len(chats)


def _migrate_qa_log(user_id: str) -> int:
    if not QALOG_DB.exists():
        print("no qa_log.db — skipping qa_log")
        return 0
    con = sqlite3.connect(QALOG_DB)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            "SELECT id, ts, question, answer, tool_calls, sources, kb_hit, feedback FROM qa_log"
        ).fetchall()
    finally:
        con.close()

    def _loads(val):
        try:
            return json.loads(val) if val else []
        except (TypeError, json.JSONDecodeError):
            return []

    with session_scope() as s:
        for r in rows:
            s.merge(QALogRow(
                id=r["id"], user_id=user_id, ts=r["ts"] or 0.0,
                question=r["question"] or "", answer=r["answer"] or "",
                tool_calls=_loads(r["tool_calls"]), sources=_loads(r["sources"]),
                kb_hit=bool(r["kb_hit"]), feedback=r["feedback"] or 0,
            ))
        # keep the id sequence ahead of the explicit ids we just inserted (Postgres only)
        try:
            s.execute(text(
                "SELECT setval(pg_get_serial_sequence('qa_log','id'), "
                "(SELECT COALESCE(MAX(id), 1) FROM qa_log))"
            ))
        except Exception:
            pass
    print(f"imported {len(rows)} qa_log rows")
    return len(rows)


def main() -> None:
    user_id = get_settings().default_user_id
    print(f"migrating into user_id={user_id!r}")
    init_db()
    UserRepo().ensure(user_id, name=get_settings().smartcat_user_name,
                      email=get_settings().smartcat_user_email or None)
    _migrate_chats(user_id)
    _migrate_qa_log(user_id)
    print("migration complete.")


if __name__ == "__main__":
    main()
