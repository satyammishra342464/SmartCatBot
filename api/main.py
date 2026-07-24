"""FastAPI backend for SmartCAT. Wraps the service layer so any client (web,
Slack, scripts) can consume the agent. Blocking agent/DB calls use sync `def`
handlers so Starlette offloads them to its threadpool."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile

import service.chat_service as svc
from api.deps import get_user_id
from api.schemas import (
    ChatObject, ChatRequest, ChatResponse, FeedbackRequest, HealthResponse,
    PrefsBody, UploadResponse,
)
from service.resources import get_resources


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.status = svc.init_service()  # create tables + wire cache (best-effort)
    try:
        get_resources()  # warm the index / Gemini client once
        app.state.resources_ok = True
    except Exception as exc:  # noqa: BLE001
        app.state.resources_ok = False
        app.state.resources_error = str(exc)
    yield


app = FastAPI(title="SmartCAT API", version="1.0", lifespan=lifespan)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    status = getattr(app.state, "status", {}) or {}
    return HealthResponse(
        status="ok",
        db=bool(status.get("db")),
        cache=bool(status.get("cache")),
        resources=bool(getattr(app.state, "resources_ok", False)),
    )


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, user_id: str = Depends(get_user_id)) -> ChatResponse:
    result = svc.chat(user_id, req.session_id, req.question, req.history)
    return ChatResponse(**result)


@app.post("/upload", response_model=UploadResponse)
def upload(
    session_id: str = Form("default"),
    files: list[UploadFile] = File(...),
    user_id: str = Depends(get_user_id),
) -> UploadResponse:
    payload = [(f.filename or "upload", f.file.read()) for f in files]
    indexed, errors = svc.upload(user_id, session_id, payload)
    return UploadResponse(indexed=indexed, errors=errors)


@app.post("/feedback")
def feedback(req: FeedbackRequest, user_id: str = Depends(get_user_id)) -> dict:
    svc.feedback(user_id, req.log_id, req.value)
    return {"ok": True}


@app.get("/chats", response_model=list[ChatObject])
def list_chats(user_id: str = Depends(get_user_id)) -> list[ChatObject]:
    return [ChatObject(**c) for c in svc.list_chats(user_id)]


@app.get("/chats/{chat_id}", response_model=ChatObject)
def get_chat(chat_id: str, user_id: str = Depends(get_user_id)) -> ChatObject:
    chat_obj = svc.get_chat(user_id, chat_id)
    if chat_obj is None:
        raise HTTPException(status_code=404, detail="chat not found")
    return ChatObject(**chat_obj)


@app.post("/chats", response_model=ChatObject)
def save_chat(chat_obj: ChatObject, user_id: str = Depends(get_user_id)) -> ChatObject:
    svc.save_chat(user_id, chat_obj.model_dump())
    return chat_obj


@app.delete("/chats/{chat_id}")
def delete_chat(chat_id: str, user_id: str = Depends(get_user_id)) -> dict:
    svc.delete_chat(user_id, chat_id)
    return {"ok": True}


@app.get("/prefs")
def get_prefs(user_id: str = Depends(get_user_id)) -> dict:
    return svc.get_prefs(user_id)


@app.put("/prefs")
def set_prefs(body: PrefsBody, user_id: str = Depends(get_user_id)) -> dict:
    svc.set_prefs(user_id, body.data)
    return {"ok": True}
