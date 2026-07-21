#!/usr/bin/env python3
"""Run the golden eval set against the agent and report accuracy.

A question passes when every expected fact appears (case-insensitive substring)
in the agent's answer.

Usage:
  python scripts/run_evals.py            # full set
  python scripts/run_evals.py --limit 5  # first N questions
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

from core.agent import run_agent
from core.code_db import CodeDB
from core.geo_db import GeoDB
from core.knowledge_index import KnowledgeIndex

load_dotenv(ROOT / ".env")

sys.path.insert(0, str(ROOT / "scripts"))
from ask import build_cli_tools  # noqa: E402

GOLDEN = ROOT / "evals" / "golden.jsonl"
INDEX_DIR = ROOT / "data" / "index"


def main() -> None:
    ap = argparse.ArgumentParser(description="Run golden evals")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    cases = [json.loads(line) for line in GOLDEN.read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.limit:
        cases = cases[: args.limit]

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        sys.exit("GEMINI_API_KEY missing in .env")
    from google import genai

    client = genai.Client(api_key=api_key)
    embed_model = os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-2")
    chat_model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
    index = KnowledgeIndex(INDEX_DIR).load()
    db = CodeDB(INDEX_DIR / "codes.db")
    geo = GeoDB(INDEX_DIR / "codes.db")
    tools = build_cli_tools(client, index, db, geo, embed_model, chat_model)

    passed = 0
    for i, case in enumerate(cases, 1):
        result = None
        for attempt in range(3):
            try:
                result = run_agent(case["question"], history=[], client=client,
                                   model=chat_model, tools=tools)
                break
            except Exception as exc:
                print(f"[{i:02d}] attempt {attempt + 1} failed ({exc}) — retrying...")
                import time
                time.sleep(5 * (attempt + 1))
        if result is None:
            print(f"[{i:02d}/{len(cases)}] ERROR — {case['question']}")
            continue
        answer_lower = result.answer.lower()
        missing = [f for f in case["expected_facts"] if f.lower() not in answer_lower]
        ok = not missing
        passed += ok
        status = "PASS" if ok else f"FAIL (missing: {', '.join(missing)})"
        print(f"[{i:02d}/{len(cases)}] {status} — {case['question']}")

    print(f"\nScore: {passed}/{len(cases)} ({100 * passed / len(cases):.0f}%)")


if __name__ == "__main__":
    main()
