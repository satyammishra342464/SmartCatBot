# SmartCAT — Agentic CAT Modelling Chatbot (POC)

An agentic RAG chatbot for CAT modelling Q&A. Knowledge base: the official
**UNICEDE (Verisk/AIR)** reference + **OED (Open Exposure Data)** spec +
internal training docs (e.g. RMS RiskLink slip coding rules). Falls back to
**live web search**, then to labeled general knowledge. Never invents codes —
numeric codes are verified against the code DB before being stated.

## Agent tools

| Tool | What it does |
|---|---|
| `search_knowledge` | Hybrid (vector + keyword, RRF-fused) search over the corpus |
| `lookup_codes` | Exact search over 39k+ code-table rows (SQLite FTS5) |
| `web_search` | Live Google search via Gemini grounding (labeled 🌐) |
| `calculate` | Safe arithmetic (layer losses, deductibles, percentages) |
| `lookup_location` | GeoNames postal/pincode lookups |
| `search_uploaded_docs` | Q&A over documents uploaded in the current session |

## Architecture

```
UNICEDE crawl ─┐
OED GitHub ────┤→ data/corpus/*.json ─→ Vector index (gemini-embedding-2 + numpy, hybrid search)
local_docs ────┘                      └→ SQLite: code_rows (FTS5) + postal_codes (GeoNames)
                                                     ▼
                        Agent (Gemini function calling, 6-tool registry, forced final answer)
                                                     ▼
                  Streamlit UI: streaming answers · trace · 👍/👎 feedback · uploads
                                     (all Q&A logged to qa_log.db)
```

## Setup & run

```powershell
cd DocChatbot
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
# .env must contain: GEMINI_API_KEY=...

.venv\Scripts\python scripts\crawl_unicede.py      # 1) crawl UNICEDE (~25 min, resumable)
.venv\Scripts\python scripts\ingest_oed.py         # 2) OED spec from GitHub (optional)
.venv\Scripts\python scripts\ingest_docs.py        #    + any files in data/local_docs/
.venv\Scripts\python scripts\build_stores.py       # 3) build vector index + code DB
.venv\Scripts\python scripts\ingest_geonames.py    # 4) postal codes (optional, ~1.7M rows)
.venv\Scripts\streamlit run app.py                 # 5) chat UI
```

Quick checks: `scripts\ask.py "question"` (CLI), `scripts\run_evals.py` (golden set accuracy).

## Scalable backend (FastAPI + Postgres + Redis)

The agent logic lives in a shared **service layer** (`service/`) consumed by both the
Streamlit UI and a **FastAPI** backend (`api/`). Per-user chats, prefs, QA log, and
uploaded-doc chunks live in **Postgres**; embeddings and repeated answers are cached in
**Redis**. The knowledge base (codes.db + numpy index) stays shared and read-only.

```
core/ (stores, agent) -> service/ (orchestration + cache) -> api/ (FastAPI) + app.py (Streamlit)
                                     |                              |
                        Redis (embed/response cache)   Postgres (users, chats, qa_log, prefs, uploads)
```

Run it:

```powershell
docker compose up -d                                 # 1) start Postgres + Redis
# copy .env.example keys DATABASE_URL / REDIS_URL into your .env
.venv\Scripts\python scripts\init_db.py              # 2) create tables
.venv\Scripts\python scripts\migrate_chats_to_db.py  # 3) import old chats.json + qa_log.db (optional)
.venv\Scripts\uvicorn api.main:app --port 8000       # 4a) REST backend -> http://localhost:8000/docs
.venv\Scripts\streamlit run app.py                   # 4b) UI (now persists to Postgres)
```

Both front-ends work independently. API identity is the `X-User-Id` header (defaults to
`SMARTCAT_USER_EMAIL`); Streamlit uses `SMARTCAT_USER_EMAIL`. Example call:

```bash
curl -X POST localhost:8000/chat -H "Content-Type: application/json" \
  -H "X-User-Id: you@example.com" \
  -d '{"question":"What are the sub-perils of Earthquake?","session_id":"s1"}'
```

Tests (no infra needed — run against SQLite): `.venv\Scripts\python -m pytest tests/`

## Adding knowledge

- **Any document**: drop PDF/DOCX/TXT/MD/CSV/XLSX into `data/local_docs/` → `ingest_docs.py` → `build_stores.py`
- **Session-only**: upload via the UI sidebar ("Chat with your document") — indexed in memory, gone on restart
- **Keep UNICEDE fresh**: `scripts\refresh_corpus.py` re-crawls only when the site's What's-new pages change.
  Schedule it monthly (run once in an admin PowerShell):

  ```powershell
  schtasks /Create /SC MONTHLY /D 1 /ST 09:00 /TN "SmartCAT Corpus Refresh" `
    /TR "C:\Users\satyam342464\Desktop\DocChatbot\.venv\Scripts\python.exe C:\Users\satyam342464\Desktop\DocChatbot\scripts\refresh_corpus.py"
  ```

## Evals & logging

- `evals/golden.jsonl` — golden Q&A set (extend it as you find gaps); `run_evals.py` reports accuracy
- Every UI question is logged to `data/index/qa_log.db` with tool trace + 👍/👎 feedback —
  questions with `kb_hit = 0` show where the knowledge base needs new sources

## Enterprise path

Done (see "Scalable backend" above):
- ✅ FastAPI wrapper over `core/` (`/chat`, `/upload`, `/feedback`, `/chats`, `/prefs`) — SmartCAT or any client can consume it
- ✅ Per-user data (chats, prefs, QA log, uploads) in PostgreSQL
- ✅ Redis caching for embeddings + repeated answers

Remaining:
- numpy index → pgvector (the knowledge base is still numpy + SQLite reference data)
- Real authentication (currently the `X-User-Id` header / env user — no login yet)
- Gemini API → Vertex AI for enterprise data terms
- Real token streaming from the agent (UI streaming is currently simulated)
- Manual-download sources when available: CEDE schema (Verisk), CRESTA.org Excel (drop into `data/local_docs/`)
