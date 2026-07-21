#!/usr/bin/env python3
"""CLI test for the agent: python scripts/ask.py "Australia ka country code kya hai?" """
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

from core.agent import run_agent
from core.calculator import calculate
from core.code_db import CodeDB
from core.geo_db import GeoDB
from core.knowledge_index import KnowledgeIndex
from core.web_search import make_web_search

load_dotenv(ROOT / ".env")

INDEX_DIR = ROOT / "data" / "index"


def build_cli_tools(client, index, db, geo, embed_model, chat_model) -> dict:
    tools = {
        "search_knowledge": lambda q: [
            {"title": h["title"], "url": h["url"], "version": h.get("version"),
             "excerpt": h["text"][:1500]}
            for h in index.search(q, client, embed_model, top_k=10)
        ],
        "lookup_codes": lambda q: db.search(q, top_k=12),
        "web_search": make_web_search(client, chat_model),
        "calculate": calculate,
    }
    if geo.available:
        tools["lookup_location"] = lambda q: geo.search(q, top_k=10)
    return tools


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit('Usage: python scripts/ask.py "your question"')
    question = sys.argv[1]

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

    result = run_agent(
        question, history=[], client=client, model=chat_model,
        tools=build_cli_tools(client, index, db, geo, embed_model, chat_model),
    )

    print("=== TOOL CALLS ===")
    for call in result.tool_calls:
        print(f"  {call['tool']}({call['query']!r}) -> {call['hits']} hits")
    print("=== ANSWER ===")
    print(result.answer)
    if result.sources:
        print("=== SOURCES ===")
        seen = set()
        for src in result.sources:
            if src["url"] not in seen:
                seen.add(src["url"])
                print(f"  {src['title']} — {src['url']}")


if __name__ == "__main__":
    main()
