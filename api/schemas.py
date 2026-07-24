"""Pydantic request/response models for the API."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str
    session_id: str = "default"
    history: list[dict] = Field(default_factory=list)


class ChatResponse(BaseModel):
    answer: str
    sources: list[dict] = Field(default_factory=list)
    tool_calls: list[dict] = Field(default_factory=list)
    log_id: int | None = None
    cached: bool = False


class FeedbackRequest(BaseModel):
    log_id: int
    value: int  # 1 = up, -1 = down


class UploadResponse(BaseModel):
    indexed: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class ChatObject(BaseModel):
    id: str
    title: str = ""
    ts: float = 0.0
    messages: list[dict] = Field(default_factory=list)


class PrefsBody(BaseModel):
    data: dict = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: str
    db: bool = False
    cache: bool = False
    resources: bool = False
