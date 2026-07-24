"""SQLAlchemy 2.0 models for per-user application data.

JSON columns use JSONB on Postgres and fall back to generic JSON elsewhere
(so tests can run against SQLite)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# JSONB on Postgres, plain JSON on SQLite/others.
JSONType = JSON().with_variant(JSONB(), "postgresql")

# BIGSERIAL on Postgres; INTEGER PRIMARY KEY on SQLite (required for its
# rowid autoincrement — plain BIGINT PKs don't autoincrement on SQLite).
BigIntPK = BigInteger().with_variant(Integer, "sqlite")


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(320), primary_key=True)  # email (lowercase)
    name: Mapped[str | None] = mapped_column(String(256))
    email: Mapped[str | None] = mapped_column(String(320))
    password_hash: Mapped[str | None] = mapped_column(Text)  # NULL = not yet registered via auth
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # existing 12-hex id
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(256), default="")
    ts: Mapped[float] = mapped_column(Float, default=0.0)  # epoch, mirrors chats.json "ts"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="chat", cascade="all, delete-orphan", order_by="Message.position"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    chat_id: Mapped[str] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text, default="")
    trace: Mapped[dict | None] = mapped_column(JSONType)
    log_id: Mapped[int | None] = mapped_column(BigInteger)
    feedback: Mapped[int | None] = mapped_column(Integer)

    chat: Mapped[Chat] = relationship(back_populates="messages")


class QALogRow(Base):
    __tablename__ = "qa_log"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(320), index=True)
    ts: Mapped[float] = mapped_column(Float)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    tool_calls: Mapped[list | None] = mapped_column(JSONType)
    sources: Mapped[list | None] = mapped_column(JSONType)
    kb_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    feedback: Mapped[int] = mapped_column(Integer, default=0)


class Prefs(Base):
    __tablename__ = "prefs"

    user_id: Mapped[str] = mapped_column(String(320), primary_key=True)
    data: Mapped[dict] = mapped_column(JSONType, default=dict)


class UploadedDoc(Base):
    __tablename__ = "uploaded_docs"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(320), index=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    doc_name: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    chunks: Mapped[list["UploadedChunk"]] = relationship(
        back_populates="doc", cascade="all, delete-orphan"
    )


class UploadedChunk(Base):
    __tablename__ = "uploaded_chunks"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    doc_id: Mapped[int] = mapped_column(ForeignKey("uploaded_docs.id", ondelete="CASCADE"), index=True)
    doc_name: Mapped[str] = mapped_column(String(512))
    page: Mapped[int | None] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list | None] = mapped_column(JSONType)  # list[float] or None

    doc: Mapped[UploadedDoc] = relationship(back_populates="chunks")
