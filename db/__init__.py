"""Postgres persistence for per-user application data (users, chats, messages,
QA log, prefs, uploaded-doc chunks). The knowledge base (codes.db, embeddings)
stays in core/ — this package holds only per-user, write-heavy data."""
