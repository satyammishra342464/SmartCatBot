"""Core package. On import, trust the OS certificate store so HTTPS works
behind the corporate TLS-intercepting proxy (no-op if truststore is absent)."""
try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass
