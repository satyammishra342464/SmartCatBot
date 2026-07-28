"""Shared FastAPI dependencies."""
from __future__ import annotations

from fastapi import Header, HTTPException

from service.config import get_settings


def get_user_id(
    x_api_key: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
) -> str:
    """Resolve caller identity.

    Two paths:
    - Widget / external tool  →  sends X-API-Key header
    - Internal / Streamlit    →  sends X-User-Id header (or nothing)

    If SMARTCAT_API_KEY is configured in .env, every X-API-Key call is
    validated against it.  If the env var is empty the API is open (dev mode).
    """
    settings = get_settings()

    if x_api_key is not None:
        configured = settings.smartcat_api_key
        if configured and x_api_key != configured:
            raise HTTPException(status_code=401, detail="Invalid API key.")
        return settings.default_user_id   # all widget callers share the default user

    return x_user_id or settings.default_user_id
