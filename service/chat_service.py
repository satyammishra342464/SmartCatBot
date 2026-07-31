"""Service layer: the single orchestration surface used by BOTH the FastAPI
backend and Streamlit. All chat, upload, feedback, and persistence go through here."""
from __future__ import annotations

import hashlib
import hmac
import os

# ----------------------------------------------------------------- response cache
# Simple in-memory cache — keyed by normalised question text.
# Only used when history is empty and no uploaded docs are in play,
# so the answer is guaranteed to be context-independent.
_response_cache: dict[str, dict] = {}
_CACHE_MAX = 200  # keep memory bounded


def _cache_key(question: str) -> str:
    return hashlib.sha256(question.strip().lower().encode()).hexdigest()


def _cache_get(question: str) -> dict | None:
    return _response_cache.get(_cache_key(question))


def _cache_set(question: str, result: dict) -> None:
    if len(_response_cache) >= _CACHE_MAX:
        # evict oldest entry
        _response_cache.pop(next(iter(_response_cache)))
    _response_cache[_cache_key(question)] = result

from core.agent import run_agent
from core.calculator import calculate
from core.chunker import chunk_blocks
from core.loader import load_document
from core.vector_store import VectorStore
from core.web_search import make_web_search
from db.engine import init_db
from db.repositories import AuthRepo, ChatRepo, PrefsRepo, QALogRepo, UploadRepo
from service.resources import UPLOAD_DIR, Resources, get_resources

_chat_repo = ChatRepo()
_prefs_repo = PrefsRepo()
_qa_repo = QALogRepo()
_upload_repo = UploadRepo()
_auth_repo = AuthRepo()


# ----------------------------------------------------------------- bootstrap

def init_service() -> dict:
    """Create all DB tables (idempotent). Returns status dict."""
    status = {"db": False}
    init_db()
    status["db"] = True
    return status


# ----------------------------------------------------------------- auth

def _hash_pw(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 260_000)
    return salt.hex() + ":" + dk.hex()


def _verify_pw(password: str, stored: str) -> bool:
    try:
        salt_hex, dk_hex = stored.split(":", 1)
        salt = bytes.fromhex(salt_hex)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 260_000)
        return hmac.compare_digest(dk.hex(), dk_hex)
    except Exception:
        return False


def auth_register(name: str, email: str, password: str) -> dict | None:
    """Register a new user. Returns user dict on success, None if email already taken."""
    email = email.strip().lower()
    name = name.strip()
    pw_hash = _hash_pw(password)
    if _auth_repo.register(name, email, pw_hash):
        return {"id": email, "name": name, "email": email}
    return None


def auth_login(email: str, password: str) -> dict | None:
    """Authenticate. Returns user dict on success, None on bad credentials."""
    email = email.strip().lower()
    user = _auth_repo.get_by_email(email)
    if user and user["password_hash"] and _verify_pw(password, user["password_hash"]):
        return {"id": user["id"], "name": user["name"], "email": user["email"]}
    return None


def update_user_name(user_id: str, new_name: str) -> None:
    _auth_repo.update_name(user_id, new_name)


def reset_password(email: str, new_password: str) -> bool:
    """Reset password by email only (no old password required — forgot-password flow)."""
    user = _auth_repo.get_by_email(email.strip().lower())
    if not user:
        return False
    _auth_repo.update_password(user["id"], _hash_pw(new_password))
    return True


def change_password(user_id: str, old_password: str, new_password: str) -> bool:
    user = _auth_repo.get_by_email(user_id)
    if not user or not user["password_hash"]:
        return False
    if not _verify_pw(old_password, user["password_hash"]):
        return False
    _auth_repo.update_password(user_id, _hash_pw(new_password))
    return True


# ----------------------------------------------------------------- tools

def build_tools(res: Resources, session_store: VectorStore | None) -> dict:
    """Reconstruct the agent's tool registry, including uploaded-doc search when present."""
    client, index, db, geo = res.client, res.index, res.code_db, res.geo
    tools = {
        "search_knowledge": lambda q: [
            {"title": h["title"], "url": h["url"], "version": h.get("version"),
             "excerpt": h["text"][:1500]}
            for h in index.search(q, client, res.embed_model, top_k=5)
        ],
        "lookup_codes": lambda q: db.search(q, top_k=6),
        "web_search": make_web_search(client, res.chat_model),
        "calculate": calculate,
    }
    if getattr(geo, "available", False):
        tools["lookup_location"] = lambda q: geo.search(q, top_k=5)
    if session_store is not None and session_store.documents:
        tools["search_uploaded_docs"] = lambda q: [
            {"doc": h["doc"], "page": h.get("page"), "excerpt": h["text"][:1500]}
            for h in session_store.search(q, client, res.embed_model, top_k=6)
        ]
    return tools


def _load_session_store(user_id: str, session_id: str) -> VectorStore:
    store = VectorStore(None)
    store.chunks = _upload_repo.list_chunks(user_id, session_id)
    return store


def _dedup_sources(sources: list[dict]) -> list[dict]:
    seen, out = set(), []
    for src in sources or []:
        url = src.get("url")
        key = url or id(src)
        if key not in seen:
            seen.add(key)
            out.append(src)
    return out


# ----------------------------------------------------------------- chat

def chat(user_id: str, session_id: str, question: str,
         history: list[dict] | None = None) -> dict:
    """Run the agent for one question. Returns {answer, sources, tool_calls, log_id}."""
    res = get_resources()
    history = history or []
    session_store = _load_session_store(user_id, session_id)
    has_uploads = bool(session_store.chunks)

    # Cache hit: only when no conversation history and no uploaded docs in play
    if not history and not has_uploads:
        cached = _cache_get(question)
        if cached:
            return {**cached, "cached": True}

    tools = build_tools(res, session_store)
    result = run_agent(question, history=history, client=res.client,
                       model=res.chat_model, tools=tools)
    sources = _dedup_sources(result.sources)
    log_id = _qa_repo.log(user_id, question, result.answer, result.tool_calls, sources)
    out = {"answer": result.answer, "sources": sources,
           "tool_calls": result.tool_calls, "log_id": log_id, "cached": False}

    # Store in cache only for history-free, upload-free queries
    if not history and not has_uploads:
        _cache_set(question, out)

    return out


# ----------------------------------------------------------------- uploads

def _safe_name(user_id: str, session_id: str, name: str) -> str:
    base = os.path.basename(name).replace("/", "_").replace("\\", "_") or "upload"
    prefix = "".join(ch for ch in f"{user_id}_{session_id}" if ch.isalnum())[:40]
    return f"{prefix}__{base}"


def upload(user_id: str, session_id: str,
           files: list[tuple[str, bytes]]) -> tuple[list[str], list[str]]:
    """Embed and persist uploaded documents. Returns (indexed descriptions, errors)."""
    res = get_resources()
    indexed, errors = [], []
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    for name, data in files:
        try:
            target = UPLOAD_DIR / _safe_name(user_id, session_id, name)
            target.write_bytes(data)
            blocks = load_document(target)
            chunks = chunk_blocks(blocks, name)
            store = VectorStore(None)
            count = store.add_document(name, chunks, res.client, res.embed_model)
            _upload_repo.add_doc(user_id, session_id, name, store.chunks)
            indexed.append(f"{name} ({count} chunks)")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{name}: {exc}")
    return indexed, errors


def session_documents(user_id: str, session_id: str) -> dict[str, int]:
    return _upload_repo.documents(user_id, session_id)


def clear_session_documents(user_id: str, session_id: str) -> None:
    _upload_repo.clear(user_id, session_id)


# ----------------------------------------------------------------- feedback / QA

def feedback(user_id: str, log_id: int, value: int) -> None:
    _qa_repo.set_feedback(log_id, value)


def qa_stats(user_id: str | None = None) -> dict:
    return _qa_repo.stats(user_id)


# ----------------------------------------------------------------- chat CRUD

def list_chats(user_id: str) -> list[dict]:
    return _chat_repo.list_for_user(user_id)


def get_chat(user_id: str, chat_id: str) -> dict | None:
    return _chat_repo.get(user_id, chat_id)


def save_chat(user_id: str, chat_obj: dict, name: str | None = None,
              email: str | None = None) -> None:
    _chat_repo.save(user_id, chat_obj, name=name, email=email)


def delete_chat(user_id: str, chat_id: str) -> None:
    _chat_repo.delete(user_id, chat_id)


# ----------------------------------------------------------------- prefs

def get_prefs(user_id: str) -> dict:
    return _prefs_repo.get(user_id)


def set_prefs(user_id: str, data: dict) -> None:
    _prefs_repo.set(user_id, data)
