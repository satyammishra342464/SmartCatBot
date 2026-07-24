"""Service layer: orchestration between the core stores, Postgres, and Redis.

Importing this package pulls in ``core`` first, which injects truststore into
the SSL context so outbound HTTPS (Gemini) works behind a corporate proxy.
"""
import core  # noqa: F401  (import for the truststore side effect)
