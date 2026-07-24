"""Repositories: all DB access goes through these. Each method opens its own
transactional session and returns plain dicts, so callers never touch ORM
objects or sessions (safe under the FastAPI threadpool / Streamlit reruns)."""
from __future__ import annotations

import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.engine import session_scope
from db.models import (
    Chat, Message, Prefs, QALogRow, UploadedChunk, UploadedDoc, User,
)


def _ensure_user(session: Session, user_id: str, name: str | None = None,
                 email: str | None = None) -> None:
    if session.get(User, user_id) is None:
        session.add(User(
            id=user_id, name=name,
            email=email or (user_id if "@" in user_id else None),
        ))
        session.flush()


def _message_to_dict(m: Message) -> dict:
    d: dict = {"role": m.role, "content": m.content}
    if m.trace is not None:
        d["trace"] = m.trace
    if m.log_id is not None:
        d["log_id"] = m.log_id
    if m.feedback is not None:
        d["feedback"] = m.feedback
    return d


def _chat_to_dict(c: Chat) -> dict:
    return {
        "id": c.id, "title": c.title, "ts": c.ts,
        "messages": [_message_to_dict(m) for m in c.messages],
    }


class UserRepo:
    def ensure(self, user_id: str, name: str | None = None, email: str | None = None) -> None:
        with session_scope() as s:
            _ensure_user(s, user_id, name, email)


class AuthRepo:
    def register(self, name: str, email: str, password_hash: str) -> bool:
        """Register a new user. Returns True on success.
        Also succeeds if the user exists but has no password yet (migration case)."""
        with session_scope() as s:
            existing = s.get(User, email)
            if existing is None:
                s.add(User(id=email, name=name, email=email, password_hash=password_hash))
                return True
            if existing.password_hash:
                return False  # already registered
            # User exists from migration but has no password — let them set one
            existing.name = name or existing.name
            existing.password_hash = password_hash
            return True

    def get_by_email(self, email: str) -> dict | None:
        with session_scope() as s:
            u = s.get(User, email)
            if u is None:
                return None
            return {"id": u.id, "name": u.name or "", "email": u.email or "",
                    "password_hash": u.password_hash or ""}


class ChatRepo:
    def list_for_user(self, user_id: str) -> list[dict]:
        with session_scope() as s:
            chats = s.scalars(
                select(Chat).where(Chat.user_id == user_id).order_by(Chat.ts.desc())
            ).all()
            return [_chat_to_dict(c) for c in chats]

    def get(self, user_id: str, chat_id: str) -> dict | None:
        with session_scope() as s:
            c = s.get(Chat, chat_id)
            if c is None or c.user_id != user_id:
                return None
            return _chat_to_dict(c)

    def save(self, user_id: str, chat: dict, name: str | None = None,
             email: str | None = None) -> None:
        """Upsert one chat and replace its messages — the per-chat, per-user
        equivalent of chats.json's wholesale rewrite, without the global race."""
        with session_scope() as s:
            _ensure_user(s, user_id, name, email)
            c = s.get(Chat, chat["id"])
            if c is None:
                c = Chat(id=chat["id"], user_id=user_id)
                s.add(c)
            elif c.user_id != user_id:
                raise PermissionError("chat belongs to another user")
            c.title = (chat.get("title") or "")[:256]
            c.ts = float(chat.get("ts") or time.time())
            c.messages.clear()
            s.flush()
            for i, m in enumerate(chat.get("messages", [])):
                c.messages.append(Message(
                    position=i, role=m.get("role", ""), content=m.get("content", ""),
                    trace=m.get("trace"), log_id=m.get("log_id"), feedback=m.get("feedback"),
                ))

    def delete(self, user_id: str, chat_id: str) -> None:
        with session_scope() as s:
            c = s.get(Chat, chat_id)
            if c is not None and c.user_id == user_id:
                s.delete(c)


class QALogRepo:
    """Postgres-backed replacement for core.qa_log.QALog, plus a user_id column."""

    def log(self, user_id: str, question: str, answer: str,
            tool_calls: list, sources: list) -> int:
        kb_hit = any((c.get("hits", 0) or 0) > 0 for c in (tool_calls or []))
        with session_scope() as s:
            row = QALogRow(
                user_id=user_id, ts=time.time(), question=question, answer=answer,
                tool_calls=tool_calls, sources=sources, kb_hit=kb_hit, feedback=0,
            )
            s.add(row)
            s.flush()
            return row.id

    def set_feedback(self, log_id: int, feedback: int) -> None:
        with session_scope() as s:
            row = s.get(QALogRow, log_id)
            if row is not None:
                row.feedback = feedback

    def stats(self, user_id: str | None = None) -> dict:
        with session_scope() as s:
            q = select(QALogRow)
            if user_id:
                q = q.where(QALogRow.user_id == user_id)
            rows = s.scalars(q).all()
            return {
                "total": len(rows),
                "up": sum(1 for r in rows if r.feedback == 1),
                "down": sum(1 for r in rows if r.feedback == -1),
            }


class PrefsRepo:
    def get(self, user_id: str) -> dict:
        with session_scope() as s:
            p = s.get(Prefs, user_id)
            return dict(p.data) if p and p.data else {}

    def set(self, user_id: str, data: dict) -> None:
        with session_scope() as s:
            _ensure_user(s, user_id)
            p = s.get(Prefs, user_id)
            if p is None:
                s.add(Prefs(user_id=user_id, data=data))
            else:
                p.data = data


class UploadRepo:
    def add_doc(self, user_id: str, session_id: str, doc_name: str,
                chunks: list[dict]) -> int:
        """Persist a document's chunks (with embeddings), replacing any prior
        version of the same doc in this session. Returns the chunk count."""
        with session_scope() as s:
            _ensure_user(s, user_id)
            for d in s.scalars(select(UploadedDoc).where(
                UploadedDoc.user_id == user_id,
                UploadedDoc.session_id == session_id,
                UploadedDoc.doc_name == doc_name,
            )).all():
                s.delete(d)
            s.flush()
            doc = UploadedDoc(user_id=user_id, session_id=session_id, doc_name=doc_name)
            s.add(doc)
            s.flush()
            for c in chunks:
                s.add(UploadedChunk(
                    doc_id=doc.id, doc_name=doc_name, page=c.get("page"),
                    text=c.get("text", ""), embedding=c.get("embedding"),
                ))
            return len(chunks)

    def list_chunks(self, user_id: str, session_id: str) -> list[dict]:
        """Return chunks in core.VectorStore shape: {doc, page, text, embedding?}."""
        with session_scope() as s:
            docs = s.scalars(select(UploadedDoc).where(
                UploadedDoc.user_id == user_id, UploadedDoc.session_id == session_id,
            )).all()
            out: list[dict] = []
            for d in docs:
                for ch in d.chunks:
                    item: dict = {"doc": d.doc_name, "page": ch.page, "text": ch.text}
                    if ch.embedding is not None:
                        item["embedding"] = ch.embedding
                    out.append(item)
            return out

    def documents(self, user_id: str, session_id: str) -> dict[str, int]:
        with session_scope() as s:
            docs = s.scalars(select(UploadedDoc).where(
                UploadedDoc.user_id == user_id, UploadedDoc.session_id == session_id,
            )).all()
            return {d.doc_name: len(d.chunks) for d in docs}

    def clear(self, user_id: str, session_id: str) -> None:
        with session_scope() as s:
            for d in s.scalars(select(UploadedDoc).where(
                UploadedDoc.user_id == user_id, UploadedDoc.session_id == session_id,
            )).all():
                s.delete(d)
