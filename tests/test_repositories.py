"""Repository CRUD + per-user isolation (the core of the multi-tenant change)."""
import time

from db.repositories import ChatRepo, PrefsRepo, QALogRepo, UploadRepo


def _chat(cid, title="t", msgs=None):
    return {"id": cid, "title": title, "ts": time.time(),
            "messages": msgs or [{"role": "user", "content": "hi"}]}


def test_chat_save_list_get_delete():
    repo = ChatRepo()
    repo.save("alice@x.com", _chat("c1", "First", [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1", "trace": {"tool_calls": [], "sources": []},
         "log_id": 5, "feedback": 1},
    ]))
    chats = repo.list_for_user("alice@x.com")
    assert [c["id"] for c in chats] == ["c1"]
    got = repo.get("alice@x.com", "c1")
    assert got["title"] == "First"
    assert got["messages"][1]["content"] == "a1"
    assert got["messages"][1]["log_id"] == 5
    assert got["messages"][1]["feedback"] == 1

    repo.delete("alice@x.com", "c1")
    assert repo.list_for_user("alice@x.com") == []


def test_chat_per_user_isolation():
    repo = ChatRepo()
    repo.save("u1@x.com", _chat("shared-a", "u1 chat"))
    repo.save("u2@x.com", _chat("shared-b", "u2 chat"))
    assert [c["id"] for c in repo.list_for_user("u1@x.com")] == ["shared-a"]
    assert [c["id"] for c in repo.list_for_user("u2@x.com")] == ["shared-b"]
    # u2 cannot read u1's chat
    assert repo.get("u2@x.com", "shared-a") is None


def test_chat_message_replace_on_save():
    repo = ChatRepo()
    repo.save("bob@x.com", _chat("c2", msgs=[{"role": "user", "content": "one"}]))
    repo.save("bob@x.com", _chat("c2", msgs=[
        {"role": "user", "content": "one"}, {"role": "assistant", "content": "two"}]))
    got = repo.get("bob@x.com", "c2")
    assert [m["content"] for m in got["messages"]] == ["one", "two"]


def test_qa_log_and_feedback():
    repo = QALogRepo()
    log_id = repo.log("carol@x.com", "what is X?", "X is Y",
                      tool_calls=[{"tool": "search_knowledge", "query": "X", "hits": 3}],
                      sources=[{"url": "http://a", "title": "A"}])
    assert isinstance(log_id, int)
    repo.set_feedback(log_id, 1)
    stats = repo.stats("carol@x.com")
    assert stats["total"] >= 1 and stats["up"] >= 1


def test_qa_log_kb_hit_flag():
    repo = QALogRepo()
    lid = repo.log("d@x.com", "q", "a",
                   tool_calls=[{"tool": "calculate", "query": "1+1", "hits": 0}], sources=[])
    # kb_hit is False when no tool returned hits — smoke check it inserted
    assert isinstance(lid, int)


def test_prefs_roundtrip():
    repo = PrefsRepo()
    assert repo.get("e@x.com") == {}
    repo.set("e@x.com", {"dark_mode": True})
    assert repo.get("e@x.com") == {"dark_mode": True}
    repo.set("e@x.com", {"dark_mode": False})
    assert repo.get("e@x.com") == {"dark_mode": False}


def test_upload_persist_and_list():
    repo = UploadRepo()
    chunks = [
        {"doc": "slip.pdf", "page": 1, "text": "layer 50 xs 50", "embedding": [0.1, 0.2]},
        {"doc": "slip.pdf", "page": 2, "text": "flood peril", "embedding": [0.3, 0.4]},
    ]
    count = repo.add_doc("f@x.com", "sess1", "slip.pdf", chunks)
    assert count == 2
    listed = repo.list_chunks("f@x.com", "sess1")
    assert len(listed) == 2
    assert listed[0]["text"] and "embedding" in listed[0]
    assert repo.documents("f@x.com", "sess1") == {"slip.pdf": 2}
    # isolation by session
    assert repo.list_chunks("f@x.com", "other-sess") == []
    repo.clear("f@x.com", "sess1")
    assert repo.list_chunks("f@x.com", "sess1") == []
