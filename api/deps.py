"""Shared FastAPI dependencies."""
from __future__ import annotations

from fastapi import Header

from service.config import get_settings


def get_user_id(x_user_id: str | None = Header(default=None)) -> str:
    """Multi-tenant identity: the X-User-Id header, falling back to the configured
    default user (single-user parity with Streamlit). Real auth is future work."""
    return x_user_id or get_settings().default_user_id
