"""The optional embedding-cache hook in core, and the response-cache key."""
import core.vector_store as vs
from service.cache import response_key


class FakeCache:
    def __init__(self):
        self.store: dict = {}

    def get_many(self, keys):
        return [self.store.get(k) for k in keys]

    def set_many(self, mapping):
        self.store.update(mapping)


def test_embedding_cache_only_embeds_misses(monkeypatch):
    calls = []

    def fake_uncached(client, model, texts, task):
        calls.append(list(texts))
        return [[float(len(t))] for t in texts]

    monkeypatch.setattr(vs, "_embed_uncached", fake_uncached)
    vs.register_embedding_cache(FakeCache())
    try:
        r1 = vs._embed_texts(None, "m", ["a", "bb"], "RETRIEVAL_DOCUMENT")
        r2 = vs._embed_texts(None, "m", ["a", "bb"], "RETRIEVAL_DOCUMENT")
        r3 = vs._embed_texts(None, "m", ["a", "ccc"], "RETRIEVAL_DOCUMENT")
        assert r1 == [[1.0], [2.0]]
        assert r2 == r1                     # served from cache
        assert r3 == [[1.0], [3.0]]         # "a" cached, "ccc" fresh
        # uncached was called for: [a,bb] once, then only [ccc]
        assert calls == [["a", "bb"], ["ccc"]]
    finally:
        vs.register_embedding_cache(None)


def test_no_cache_falls_back_to_uncached(monkeypatch):
    calls = []

    def fake_uncached(client, model, texts, task):
        calls.append(list(texts))
        return [[0.0] for _ in texts]

    monkeypatch.setattr(vs, "_embed_uncached", fake_uncached)
    vs.register_embedding_cache(None)
    vs._embed_texts(None, "m", ["x"], "RETRIEVAL_QUERY")
    vs._embed_texts(None, "m", ["x"], "RETRIEVAL_QUERY")
    assert calls == [["x"], ["x"]]  # no caching → embedded both times


def test_response_key_stable_and_tool_order_independent():
    k1 = response_key("gemini-3.5-flash", "What is X?", ["a", "b"])
    k2 = response_key("gemini-3.5-flash", "  what is x?  ", ["b", "a"])
    k3 = response_key("gemini-3.5-flash", "different", ["a", "b"])
    assert k1 == k2          # normalized question + sorted tools
    assert k1 != k3
    assert k1.startswith("resp:")
