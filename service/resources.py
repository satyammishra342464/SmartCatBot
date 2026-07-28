"""Heavy, read-only shared resources built ONCE per process: the Gemini client,
the knowledge index (loaded into RAM), and the code/geo SQLite stores.

Mirrors the setup in scripts/ask.py and app.py:load_resources(), but decoupled
from Streamlit so both the FastAPI backend and Streamlit can share it."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from service.config import get_settings

ROOT = Path(__file__).resolve().parents[1]
INDEX_DIR = ROOT / "data" / "index"
UPLOAD_DIR = ROOT / "data" / "tmp_uploads"


@dataclass
class Resources:
    client: object
    index: object
    code_db: object
    geo: object
    embed_model: str
    chat_model: str


_resources: Resources | None = None


def get_resources() -> Resources:
    global _resources
    if _resources is None:
        _resources = _build()
    return _resources


def _build() -> Resources:
    from google import genai

    from core.code_db import CodeDB
    from core.geo_db import GeoDB
    from core.knowledge_index import KnowledgeIndex

    settings = get_settings()
    if not settings.api_key:
        raise RuntimeError("GEMINI_API_KEY (or GOOGLE_API_KEY) missing in environment/.env")

    client = genai.Client(api_key=settings.api_key)

    from core.loader import register_ocr_client
    register_ocr_client(client, model=settings.gemini_model)

    index = KnowledgeIndex(INDEX_DIR)
    if index.exists:
        index.load()
    code_db = CodeDB(INDEX_DIR / "codes.db")
    geo = GeoDB(INDEX_DIR / "codes.db")
    return Resources(
        client=client, index=index, code_db=code_db, geo=geo,
        embed_model=settings.gemini_embed_model, chat_model=settings.gemini_model,
    )
