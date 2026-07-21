"""SmartCAT — Agentic CAT modelling assistant (UNICEDE + internal docs + web + tools).

Theme: EXL Services palette (matches SmartCAT.Ai) with a light/dark toggle.
"""
from __future__ import annotations

import html as html_lib
import json
import os
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

import streamlit as st
from dotenv import load_dotenv

from core.agent import run_agent
from core.calculator import calculate
from core.chunker import chunk_blocks
from core.code_db import CodeDB
from core.geo_db import GeoDB
from core.knowledge_index import KnowledgeIndex
from core.loader import SUPPORTED_EXTENSIONS, load_document
from core.qa_log import QALog
from core.vector_store import VectorStore
from core.web_search import make_web_search

load_dotenv()

APP_DIR = Path(__file__).resolve().parent
INDEX_DIR = APP_DIR / "data" / "index"
UPLOAD_DIR = APP_DIR / "data" / "tmp_uploads"
CHATS_FILE = APP_DIR / "data" / "chats.json"
PREFS_FILE = APP_DIR / "data" / "ui_prefs.json"
USER_NAME = os.getenv("SMARTCAT_USER_NAME", os.getenv("USERNAME", "User"))
USER_EMAIL = os.getenv("SMARTCAT_USER_EMAIL", "")
EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-2")
CHAT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

st.set_page_config(page_title="SmartCAT — CAT Modelling Assistant", page_icon="🌀",
                   layout="wide", initial_sidebar_state="expanded")

# ------------------------------------------------------------------ EXL palette + theming

EXL_ORANGE = "#E84E0E"
EXL_ORANGE_DARK = "#C7410B"
EXL_ORANGE_HOVER = "#FF7040"


def theme_palette(dark: bool) -> dict:
    if dark:
        return {
            "BG": "#0D1117", "CARD": "#171E2B",
            "BORDER": "rgba(148, 163, 184, .20)",
            "TEXT": "#E8EAF0", "SUB": "#9AA7BD", "MID": "#7E8CA3",
            "SIDEBAR_TOP": "#141B27", "SIDEBAR_BOT": "#0D1117",
            "INPUT_BG": "#171E2B",
            "TINT": "rgba(232, 78, 14, .12)", "TINT_BORDER": "rgba(232, 78, 14, .40)",
            "BTN_BG": "#171E2B", "BTN_TEXT": "#FF9068", "BTN_HOVER_BG": "rgba(232, 78, 14, .14)",
            "CARD_SHADOW": "0 6px 22px rgba(0, 0, 0, .35)",
            "SCROLL": "#2A3446",
            "AUR1": ".10", "AUR2": ".08", "AUR3": ".05",
            "HERO_GLOW": ".26",
        }
    return {
        "BG": "#F2F2F2", "CARD": "#FFFFFF",
        "BORDER": "#DEDEDE",
        "TEXT": "#222222", "SUB": "#555555", "MID": "#888888",
        "SIDEBAR_TOP": "#FFFFFF", "SIDEBAR_BOT": "#F7F7F7",
        "INPUT_BG": "#FFFFFF",
        "TINT": "#FFF3EE", "TINT_BORDER": "rgba(232, 78, 14, .28)",
        "BTN_BG": "#FFFFFF", "BTN_TEXT": EXL_ORANGE_DARK, "BTN_HOVER_BG": "#FFF3EE",
        "CARD_SHADOW": "0 4px 16px rgba(34, 34, 34, .06)",
        "SCROLL": "#D5D5D5",
        "AUR1": ".07", "AUR2": ".06", "AUR3": ".05",
        "HERO_GLOW": ".18",
    }


def build_css(dark: bool) -> str:
    P = theme_palette(dark)
    css = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {{ font-family: 'Inter', 'Segoe UI', sans-serif; }}

/* ---------- backgrounds + aurora ---------- */
html, body {{ background: {P["BG"]} !important; }}
.stApp {{ background: transparent !important; }}
.stApp::before {{
    content: ""; position: fixed; inset: -20%; z-index: -1;
    background:
        radial-gradient(38% 30% at 20% 15%, rgba(232, 78, 14, {P["AUR1"]}), transparent 62%),
        radial-gradient(34% 30% at 80% 75%, rgba(255, 112, 64, {P["AUR2"]}), transparent 62%),
        radial-gradient(24% 20% at 65% 10%, rgba(136, 136, 136, {P["AUR3"]}), transparent 60%);
    animation: scAurora 16s ease-in-out infinite alternate;
    pointer-events: none;
}}
@keyframes scAurora {{
    0%   {{ transform: translate3d(-2.5%, -1.5%, 0) scale(1); }}
    50%  {{ transform: translate3d(2%, 2.5%, 0) scale(1.07); }}
    100% {{ transform: translate3d(-1%, 1.5%, 0) scale(1.03); }}
}}

/* ---------- app chrome: top header + bottom input bar ---------- */
[data-testid="stHeader"] {{ background: transparent !important; }}
.stDeployButton, [data-testid="stAppDeployButton"] {{ display: none !important; }}
[data-testid="stBottom"] {{
    background: {P["BG"]} !important;
}}
[data-testid="stBottom"] > div,
[data-testid="stBottomBlockContainer"] {{
    background: {P["BG"]} !important;
}}

/* ---------- chat messages ---------- */
[data-testid="stChatMessage"] {{
    animation: scFadeUp .45s cubic-bezier(.22, .9, .35, 1);
    border: 1px solid {P["BORDER"]};
    background: {P["CARD"]};
    border-radius: 16px;
    padding: 14px 16px;
    margin-bottom: 10px;
    box-shadow: {P["CARD_SHADOW"]};
    transition: border-color .3s ease, box-shadow .3s ease;
}}
[data-testid="stChatMessage"]:hover {{
    border-color: rgba(232, 78, 14, .45);
    box-shadow: 0 8px 24px rgba(232, 78, 14, .12);
}}
@keyframes scFadeUp {{
    from {{ opacity: 0; transform: translateY(14px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
}}

/* ---------- wordmark ---------- */
.sc-title {{
    font-size: 2.2rem; font-weight: 800; letter-spacing: .4px; line-height: 1.1;
    background: linear-gradient(90deg, {EXL_ORANGE}, {EXL_ORANGE_HOVER}, {EXL_ORANGE_DARK}, {EXL_ORANGE});
    background-size: 300% 100%;
    -webkit-background-clip: text; background-clip: text;
    -webkit-text-fill-color: transparent;
    animation: scGradient 9s ease infinite;
}}
@keyframes scGradient {{
    0% {{ background-position: 0% 50%; }}
    50% {{ background-position: 100% 50%; }}
    100% {{ background-position: 0% 50%; }}
}}
.sc-sub {{ color: {P["SUB"]}; font-size: .95rem; margin-top: 2px; }}
.sc-header {{ display: flex; gap: 14px; align-items: center; padding: 4px 0 10px; }}

/* ---------- hero ---------- */
.sc-hero {{
    display: flex; flex-direction: column; align-items: center; text-align: center;
    padding: 30px 0 6px; animation: scFadeUp .6s ease; position: relative;
}}
.sc-hero .sc-title {{ font-size: 3rem; animation: scGradient 9s ease infinite, scFadeUp .7s .12s both; }}
.sc-hero .sc-sub {{ animation: scFadeUp .7s .28s both; }}
.sc-hero-tags {{ color: {P["MID"]}; font-size: .92rem; margin-top: 8px; animation: scFadeUp .7s .45s both; }}
.sc-hero::before {{
    content: ""; position: absolute; top: 0; left: 50%; margin-left: -120px;
    width: 240px; height: 240px; border-radius: 50%; z-index: -1;
    background: radial-gradient(circle, rgba(232, 78, 14, {P["HERO_GLOW"]}), transparent 70%);
    filter: blur(14px);
    animation: scPulse 4.2s ease-in-out infinite;
}}
@keyframes scPulse {{
    0%, 100% {{ opacity: .5; transform: scale(1); }}
    50%      {{ opacity: 1;  transform: scale(1.18); }}
}}
.sc-hero svg {{ animation: scFloat 5.5s ease-in-out infinite; }}
@keyframes scFloat {{
    0%, 100% {{ transform: translateY(0); }}
    50%      {{ transform: translateY(-10px); }}
}}

/* ---------- chat input ---------- */
[data-testid="stChatInput"] {{
    border-radius: 14px;
    background: {P["INPUT_BG"]} !important;
    border: 1px solid {P["BORDER"]};
    transition: box-shadow .3s ease, border-color .3s ease;
    animation: scInputGlow 5.5s ease-in-out infinite;
}}
@keyframes scInputGlow {{
    0%, 100% {{ box-shadow: 0 0 0 rgba(232, 78, 14, 0); }}
    50%      {{ box-shadow: 0 0 16px rgba(232, 78, 14, .14); }}
}}
[data-testid="stChatInput"]:focus-within {{
    border-color: {EXL_ORANGE};
    animation: none;
    box-shadow: 0 0 20px rgba(232, 78, 14, .26);
}}
[data-testid="stChatInput"] > div,
[data-testid="stChatInput"] div[data-baseweb="textarea"],
[data-testid="stChatInput"] div[data-baseweb="base-input"] {{
    background: transparent !important;
    border: none !important;
}}
[data-testid="stChatInput"] textarea {{
    background: transparent !important;
    color: {P["TEXT"]} !important;
    caret-color: {EXL_ORANGE};
}}
[data-testid="stChatInput"] textarea::placeholder {{ color: {P["MID"]}; }}
[data-testid="stChatInput"] button {{
    background: transparent;
    color: {EXL_ORANGE};
    border-radius: 10px;
    transition: all .25s ease;
}}
[data-testid="stChatInput"] button:hover {{
    background: rgba(232, 78, 14, .14);
    color: {EXL_ORANGE_HOVER};
    transform: scale(1.08);
}}
[data-testid="stChatInput"] svg {{ fill: currentColor; }}

/* ---------- sidebar ---------- */
[data-testid="stSidebar"] {{
    background: linear-gradient(180deg, {P["SIDEBAR_TOP"]} 0%, {P["SIDEBAR_BOT"]} 100%);
    border-right: 1px solid {P["BORDER"]};
}}
[data-testid="stSidebar"] .sc-header svg {{ animation: scFloat 6.5s ease-in-out infinite; }}
[data-testid="stMetric"] {{
    background: {P["TINT"]};
    border: 1px solid {P["TINT_BORDER"]};
    border-radius: 14px;
    padding: 10px 14px;
    transition: transform .25s ease, box-shadow .25s ease;
}}
[data-testid="stMetric"]:hover {{ transform: translateY(-2px); box-shadow: 0 8px 18px rgba(232, 78, 14, .16); }}
[data-testid="stMetricValue"] {{ color: {P["TEXT"]}; }}
[data-testid="stMetricLabel"] {{ color: {P["SUB"]}; }}

/* ---------- expanders ---------- */
[data-testid="stExpander"] {{
    border-radius: 12px; border: 1px solid {P["BORDER"]}; background: {P["CARD"]};
    transition: border-color .3s ease, box-shadow .3s ease;
}}
[data-testid="stExpander"]:hover {{
    border-color: rgba(232, 78, 14, .5);
    box-shadow: 0 6px 16px rgba(232, 78, 14, .12);
}}
[data-testid="stExpander"] summary {{ color: {P["TEXT"]}; }}

/* ---------- buttons ---------- */
.stButton button {{
    position: relative; overflow: hidden;
    border-radius: 12px;
    border: 1px solid rgba(232, 78, 14, .45);
    background: {P["BTN_BG"]};
    color: {P["BTN_TEXT"]};
    font-weight: 600;
    transition: all .25s ease;
    animation: scFadeUp .5s both cubic-bezier(.22, .9, .35, 1);
}}
.stButton button:hover {{
    transform: translateY(-2px);
    border-color: {EXL_ORANGE};
    background: {P["BTN_HOVER_BG"]};
    color: {P["BTN_TEXT"]};
    box-shadow: 0 8px 20px rgba(232, 78, 14, .20);
}}
.stButton button::before {{
    content: ""; position: absolute; top: 0; left: -85%;
    width: 55%; height: 100%;
    background: linear-gradient(105deg, transparent, rgba(232, 78, 14, .10), transparent);
    transform: skewX(-20deg);
    transition: left .55s ease;
}}
.stButton button:hover::before {{ left: 135%; }}
.stButton button:active {{ transform: scale(.96) !important; }}
[data-testid="stMain"] [data-testid="stHorizontalBlock"] [data-testid="stColumn"]:nth-of-type(1) .stButton button {{ animation-delay: .55s; }}
[data-testid="stMain"] [data-testid="stHorizontalBlock"] [data-testid="stColumn"]:nth-of-type(2) .stButton button {{ animation-delay: .68s; }}
[data-testid="stMain"] [data-testid="stHorizontalBlock"] [data-testid="stColumn"]:nth-of-type(3) .stButton button {{ animation-delay: .81s; }}
[data-testid="stMain"] [data-testid="stHorizontalBlock"] [data-testid="stColumn"]:nth-of-type(4) .stButton button {{ animation-delay: .94s; }}

/* ---------- sidebar chat history list ---------- */
[data-testid="stSidebar"] .stButton button {{ justify-content: flex-start; }}
[data-testid="stSidebar"] .stButton button p {{
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%;
    font-size: .88rem;
}}
[class*="st-key-chat-"] button {{
    background: transparent !important;
    border-color: transparent !important;
    color: {P["TEXT"]} !important;
    animation: none !important;
}}
[class*="st-key-chat-"] button:hover {{
    background: {P["BTN_HOVER_BG"]} !important;
    border-color: rgba(232, 78, 14, .35) !important;
    box-shadow: none !important;
    transform: none !important;
}}
[class*="st-key-chat-"] button:disabled {{
    background: rgba(232, 78, 14, .14) !important;
    border: 1px solid rgba(232, 78, 14, .38) !important;
    color: {P["TEXT"]} !important;
    opacity: 1 !important;
}}
[class*="st-key-del-"] button {{
    background: transparent !important;
    border-color: transparent !important;
    color: {P["MID"]} !important;
    justify-content: center !important;
    animation: none !important;
}}
[class*="st-key-del-"] button:hover {{
    color: #E5484D !important;
    background: rgba(229, 72, 77, .12) !important;
    border-color: rgba(229, 72, 77, .40) !important;
    box-shadow: none !important;
    transform: none !important;
}}

/* ---------- account card (pinned bottom-left, ChatGPT style) ---------- */
[data-testid="stSidebarUserContent"] {{ padding-bottom: 84px; }}
.sc-account {{
    position: fixed; bottom: 14px; left: 14px; z-index: 999;
    display: flex; align-items: center; gap: 10px;
    width: 218px; padding: 9px 12px;
    border-radius: 14px;
    background: {P["CARD"]};
    border: 1px solid {P["BORDER"]};
    box-shadow: {P["CARD_SHADOW"]};
    transition: border-color .25s ease, box-shadow .25s ease;
}}
.sc-account:hover {{
    border-color: {EXL_ORANGE};
    box-shadow: 0 8px 20px rgba(232, 78, 14, .18);
}}
.sc-avatar {{
    width: 34px; height: 34px; border-radius: 50%; flex-shrink: 0;
    background: linear-gradient(135deg, {EXL_ORANGE_HOVER}, {EXL_ORANGE_DARK});
    color: #FFFFFF; display: flex; align-items: center; justify-content: center;
    font-weight: 800; font-size: .82rem; letter-spacing: .03em;
}}
.sc-account-info {{ display: flex; flex-direction: column; line-height: 1.25; overflow: hidden; }}
.sc-account-name {{ color: {P["TEXT"]}; font-size: .84rem; font-weight: 700; white-space: nowrap; }}
.sc-account-mail {{
    color: {P["MID"]}; font-size: .70rem;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 128px;
}}
.sc-account-dot {{
    width: 9px; height: 9px; border-radius: 50%; margin-left: auto; flex-shrink: 0;
    background: #22C55E; box-shadow: 0 0 8px rgba(34, 197, 94, .8);
    animation: scPulse 3s ease-in-out infinite;
}}
.stButton button[kind="primary"],
[data-testid="stBaseButton-primary"] {{
    background: {EXL_ORANGE} !important;
    color: #FFFFFF !important;
    border-color: {EXL_ORANGE} !important;
}}
.stButton button[kind="primary"]:hover {{ background: {EXL_ORANGE_DARK} !important; }}

/* ---------- source citation cards ---------- */
.sc-src-label {{
    color: {P["MID"]}; font-size: .78rem; font-weight: 700;
    text-transform: uppercase; letter-spacing: .1em; margin: 12px 0 7px;
}}
.sc-sources {{ display: flex; flex-wrap: wrap; gap: 8px; }}
.sc-src {{
    display: flex; align-items: center; gap: 9px;
    padding: 7px 14px 7px 8px;
    border: 1px solid {P["BORDER"]};
    border-radius: 12px;
    background: {P["CARD"]};
    text-decoration: none !important;
    transition: all .22s ease;
    max-width: 340px;
    animation: scFadeUp .45s both ease;
}}
.sc-src:hover {{
    transform: translateY(-2px);
    border-color: {EXL_ORANGE};
    box-shadow: 0 8px 20px rgba(232, 78, 14, .18);
}}
.sc-src-num {{
    min-width: 20px; height: 20px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    color: #FFFFFF; font-size: .72rem; font-weight: 800; flex-shrink: 0;
}}
.sc-src-icon {{ font-size: 1.05rem; flex-shrink: 0; }}
.sc-src-body {{ display: flex; flex-direction: column; line-height: 1.3; overflow: hidden; }}
.sc-src-title {{
    color: {P["TEXT"]}; font-size: .85rem; font-weight: 600;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}}
.sc-src-kind {{ color: {P["MID"]}; font-size: .72rem; }}
.sc-sources .sc-src:nth-child(1) {{ animation-delay: .05s; }}
.sc-sources .sc-src:nth-child(2) {{ animation-delay: .13s; }}
.sc-sources .sc-src:nth-child(3) {{ animation-delay: .21s; }}
.sc-sources .sc-src:nth-child(4) {{ animation-delay: .29s; }}
.sc-sources .sc-src:nth-child(5) {{ animation-delay: .37s; }}
.sc-sources .sc-src:nth-child(6) {{ animation-delay: .45s; }}
.sc-sources .sc-src:nth-child(7) {{ animation-delay: .53s; }}
.sc-sources .sc-src:nth-child(8) {{ animation-delay: .61s; }}

/* ---------- scrollbar ---------- */
::-webkit-scrollbar {{ width: 10px; height: 10px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
::-webkit-scrollbar-thumb {{
    background: {P["SCROLL"]};
    border-radius: 8px;
    border: 2px solid {P["BG"]};
}}
::-webkit-scrollbar-thumb:hover {{ background: {EXL_ORANGE}; }}
"""
    if dark:
        css += f"""
/* ---------- dark-mode text/readability overrides ---------- */
.stApp, .stApp p, .stApp li, .stMarkdown, [data-testid="stMarkdownContainer"] {{ color: {P["TEXT"]}; }}
h1, h2, h3, h4, h5, h6 {{ color: {P["TEXT"]} !important; }}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p, small {{ color: {P["SUB"]} !important; }}
code {{ background: rgba(232, 78, 14, .14); color: #FF9068; }}
hr {{ border-color: {P["BORDER"]}; }}
[data-testid="stSidebar"] {{ color-scheme: dark; }}
[data-testid="stChatInput"] {{ color-scheme: dark; }}
[data-testid="stWidgetLabel"] p {{ color: {P["TEXT"]}; }}
[data-testid="stHeader"] {{ color-scheme: dark; }}
[data-testid="stHeader"] button {{ color: {P["SUB"]} !important; }}
[data-testid="stStatusWidget"] {{ color: {P["SUB"]}; }}
"""
    return css + "</style>"


LOGO = """
<svg viewBox="0 0 120 120" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     width="{size}" height="{size}" style="flex-shrink:0">
  <defs>
    <linearGradient id="scBg{uid}" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#FF7040"/>
      <stop offset="0.55" stop-color="#E84E0E"/>
      <stop offset="1" stop-color="#C7410B"/>
    </linearGradient>
    <linearGradient id="scArm{uid}" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#FFFFFF"/>
      <stop offset="1" stop-color="#FFE1D3"/>
    </linearGradient>
  </defs>
  <rect width="120" height="120" rx="27" fill="url(#scBg{uid})"/>
  <g>
    <animateTransform attributeName="transform" type="rotate" from="0 60 60" to="360 60 60"
                      dur="16s" repeatCount="indefinite"/>
    <path id="scA{uid}" d="M60 15 C 90 15 104 42 97 61" stroke="url(#scArm{uid})"
          stroke-width="10" fill="none" stroke-linecap="round"/>
    <use xlink:href="#scA{uid}" transform="rotate(120 60 60)"/>
    <use xlink:href="#scA{uid}" transform="rotate(240 60 60)"/>
  </g>
  <circle cx="60" cy="60" r="13.5" fill="#FFFFFF"/>
  <circle cx="60" cy="60" r="6.5" fill="#222222"/>
</svg>
"""


def logo(size: int, uid: str) -> str:
    return LOGO.format(size=size, uid=uid)


def _load_prefs() -> dict:
    try:
        return json.loads(PREFS_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_prefs() -> None:
    PREFS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PREFS_FILE.write_text(
        json.dumps({"dark_mode": st.session_state.dark_pref}), encoding="utf-8"
    )


def _on_dark_toggle() -> None:
    st.session_state.dark_pref = st.session_state.dark_widget
    _save_prefs()


# Theme preference lives in its own session key (and on disk) — never tied to the
# toggle widget itself, because Streamlit drops widget state when a rerun fires
# before the widget renders (e.g. clicking "New chat" above the toggle).
if "dark_pref" not in st.session_state:
    st.session_state.dark_pref = bool(_load_prefs().get("dark_mode", False))

DARK_MODE = st.session_state.dark_pref
st.markdown(build_css(DARK_MODE), unsafe_allow_html=True)

# ------------------------------------------------------------------ resources


@st.cache_resource
def load_resources():
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return None, None, None, None, None
    from google import genai

    client = genai.Client(api_key=api_key)
    index = KnowledgeIndex(INDEX_DIR)
    if index.exists:
        index.load()
    db = CodeDB(INDEX_DIR / "codes.db")
    geo = GeoDB(INDEX_DIR / "codes.db")
    log = QALog(INDEX_DIR / "qa_log.db")
    return client, index, db, geo, log


client, index, db, geo, qa_log = load_resources()

def load_chats() -> list[dict]:
    try:
        return json.loads(CHATS_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_chats() -> None:
    CHATS_FILE.parent.mkdir(parents=True, exist_ok=True)
    CHATS_FILE.write_text(
        json.dumps(st.session_state.chats, ensure_ascii=False), encoding="utf-8"
    )


def sync_current_chat() -> None:
    """Persist the active conversation into the chat list (creates it on first message)."""
    messages = st.session_state.messages
    if not messages:
        return
    if st.session_state.current_chat_id is None:
        title = next((m["content"] for m in messages if m["role"] == "user"),
                     messages[0]["content"])
        chat = {"id": uuid.uuid4().hex[:12], "title": title[:48], "ts": time.time(),
                "messages": messages}
        st.session_state.chats.insert(0, chat)
        st.session_state.current_chat_id = chat["id"]
    else:
        for chat in st.session_state.chats:
            if chat["id"] == st.session_state.current_chat_id:
                chat["messages"] = messages
                chat["ts"] = time.time()
                break
    save_chats()


if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_store" not in st.session_state:
    st.session_state.session_store = VectorStore(None)  # in-memory, per session
if "chats" not in st.session_state:
    st.session_state.chats = load_chats()
if "current_chat_id" not in st.session_state:
    st.session_state.current_chat_id = None


def index_uploaded_files(files) -> tuple[list[str], list[str]]:
    """Index uploaded files into the session store. Returns (indexed names, errors)."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    indexed, errors = [], []
    for uploaded in files:
        try:
            target = UPLOAD_DIR / uploaded.name
            target.write_bytes(uploaded.getbuffer())
            blocks = load_document(target)
            chunks = chunk_blocks(blocks, uploaded.name)
            count = st.session_state.session_store.add_document(
                uploaded.name, chunks, client, EMBED_MODEL
            )
            indexed.append(f"{uploaded.name} ({count} chunks)")
        except Exception as exc:
            errors.append(f"{uploaded.name}: {exc}")
    return indexed, errors


# ------------------------------------------------------------------ sidebar

with st.sidebar:
    st.markdown(
        f'<div class="sc-header">{logo(46, "sb")}'
        f'<div><div class="sc-title" style="font-size:1.6rem">SmartCAT</div>'
        f'<div class="sc-sub">CAT Modelling Assistant</div></div></div>',
        unsafe_allow_html=True,
    )
    if client is None:
        st.error("GEMINI_API_KEY missing in .env")
    elif not index.exists:
        st.error("Knowledge index not built yet — run: python scripts/build_stores.py")

    if st.button("➕  New chat", use_container_width=True, type="primary"):
        sync_current_chat()
        st.session_state.messages = []
        st.session_state.current_chat_id = None
        st.rerun()

    if st.session_state.chats:
        st.caption("Chat history")
        for chat in st.session_state.chats:
            is_current = chat["id"] == st.session_state.current_chat_id
            col_open, col_del = st.columns([6, 1])
            if col_open.button(
                ("🟠 " if is_current else "") + chat["title"],
                key=f"chat-{chat['id']}",
                use_container_width=True,
                disabled=is_current,
            ):
                sync_current_chat()
                st.session_state.messages = chat["messages"]
                st.session_state.current_chat_id = chat["id"]
                st.rerun()
            if col_del.button("🗑", key=f"del-{chat['id']}", help="Delete this chat"):
                st.session_state.chats = [c for c in st.session_state.chats
                                          if c["id"] != chat["id"]]
                if is_current:
                    st.session_state.messages = []
                    st.session_state.current_chat_id = None
                save_chats()
                st.rerun()

    session_docs = st.session_state.session_store.documents
    if session_docs:
        st.divider()
        st.caption("📄 Attached this session: " + ", ".join(session_docs))

    st.divider()
    st.toggle("🌙 Dark mode", value=st.session_state.dark_pref,
              key="dark_widget", on_change=_on_dark_toggle)

    initials = "".join(word[0] for word in USER_NAME.split()[:2]).upper() or "U"
    st.markdown(
        f'<div class="sc-account"><div class="sc-avatar">{html_lib.escape(initials)}</div>'
        f'<div class="sc-account-info">'
        f'<span class="sc-account-name">{html_lib.escape(USER_NAME)}</span>'
        f'<span class="sc-account-mail">{html_lib.escape(USER_EMAIL)}</span></div>'
        f'<span class="sc-account-dot" title="Signed in"></span></div>',
        unsafe_allow_html=True,
    )

# ------------------------------------------------------------------ agent tools


def build_tools() -> dict:
    tools = {
        "search_knowledge": lambda q: [
            {"title": h["title"], "url": h["url"], "version": h.get("version"),
             "excerpt": h["text"][:1500]}
            for h in index.search(q, client, EMBED_MODEL, top_k=10)
        ],
        "lookup_codes": lambda q: db.search(q, top_k=12),
        "web_search": make_web_search(client, CHAT_MODEL),
        "calculate": calculate,
    }
    if geo.available:
        tools["lookup_location"] = lambda q: geo.search(q, top_k=10)
    if st.session_state.session_store.documents:
        tools["search_uploaded_docs"] = lambda q: [
            {"title": f"{h['doc']}" + (f" — page {h['page']}" if h.get("page") else ""),
             "url": "", "excerpt": h["text"][:1500]}
            for h in st.session_state.session_store.search(q, client, EMBED_MODEL, top_k=6)
        ]
    return tools


# ------------------------------------------------------------------ rendering helpers


def _source_meta(src: dict) -> tuple[str, str, str]:
    """Returns (icon, kind label, badge color) for a source."""
    url = src.get("url") or ""
    if not url or url.startswith("file:"):
        return "📄", "Internal document", "#B45309"
    domain = urlparse(url).netloc
    if "unicede" in domain:
        return "🌐", "UNICEDE Reference · Verisk", EXL_ORANGE
    if "github" in domain:
        return "📗", "OED Open Data Standard", "#0D7A3E"
    if "geonames" in domain:
        return "🌍", "GeoNames postal database", "#6D28D9"
    return "🔎", "Web source", "#BE185D"


def render_sources(sources: list[dict]) -> None:
    if not sources:
        return
    cards = []
    for i, src in enumerate(sources, 1):
        icon, kind, color = _source_meta(src)
        title = html_lib.escape((src.get("title") or "Source")[:75])
        inner = (
            f'<span class="sc-src-num" style="background:{color}">{i}</span>'
            f'<span class="sc-src-icon">{icon}</span>'
            f'<span class="sc-src-body"><span class="sc-src-title">{title}</span>'
            f'<span class="sc-src-kind">{html_lib.escape(kind)}</span></span>'
        )
        url = src.get("url") or ""
        if url:
            cards.append(
                f'<a class="sc-src" href="{html_lib.escape(url)}" target="_blank" '
                f'title="{html_lib.escape(url)}">{inner}</a>'
            )
        else:
            cards.append(f'<span class="sc-src">{inner}</span>')
    st.markdown(
        f'<div class="sc-src-label">📚 Sources</div><div class="sc-sources">{"".join(cards)}</div>',
        unsafe_allow_html=True,
    )


def render_trace(trace: dict) -> None:
    render_sources(trace["sources"])
    if trace["tool_calls"]:
        with st.expander("🔍 Agent trace"):
            for call in trace["tool_calls"]:
                st.markdown(f"- `{call['tool']}`(\"{call['query']}\") → {call['hits']} hits")


def render_feedback(i: int, message: dict) -> None:
    log_id = message.get("log_id")
    if not log_id:
        return
    if message.get("feedback"):
        st.caption("Thanks for the feedback ✓")
        return
    col_up, col_down, _ = st.columns([1, 1, 10])
    if col_up.button("👍", key=f"up-{st.session_state.current_chat_id}-{i}"):
        qa_log.set_feedback(log_id, 1)
        message["feedback"] = 1
        save_chats()
        st.rerun()
    if col_down.button("👎", key=f"down-{st.session_state.current_chat_id}-{i}"):
        qa_log.set_feedback(log_id, -1)
        message["feedback"] = -1
        save_chats()
        st.rerun()


# ------------------------------------------------------------------ header / hero

SUGGESTIONS = [
    "What are the sub-perils of Earthquake?",
    "Which occupancy code applies to a hospital?",
    "Which RMS field stores the blanket limit?",
    "Policy is 100M xs 25M — what is the payout for a 40M loss?",
]

picked = None
if not st.session_state.messages:
    st.markdown(
        f'<div class="sc-hero">{logo(96, "hero")}'
        f'<div class="sc-title">SmartCAT</div>'
        f'<div class="sc-sub">Your agentic CAT modelling assistant</div>'
        f'<div class="sc-hero-tags">Perils &amp; codes · UNICEDE formats · RMS slip coding rules · '
        f'live web search · document Q&amp;A · calculations</div></div>',
        unsafe_allow_html=True,
    )
    columns = st.columns(len(SUGGESTIONS))
    for col, suggestion in zip(columns, SUGGESTIONS):
        if col.button(suggestion, use_container_width=True):
            picked = suggestion
else:
    st.markdown(
        f'<div class="sc-header">{logo(40, "hd")}'
        f'<div><div class="sc-title" style="font-size:1.5rem">SmartCAT</div>'
        f'<div class="sc-sub">Ask anything about CAT modelling</div></div></div>',
        unsafe_allow_html=True,
    )

# ------------------------------------------------------------------ chat

for i, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("trace"):
            render_trace(message["trace"])
        if message["role"] == "assistant":
            render_feedback(i, message)

submitted = st.chat_input(
    "Ask SmartCAT anything — attach a slip/document with 📎 to chat about it...",
    accept_file="multiple",
    file_type=[ext.lstrip(".") for ext in SUPPORTED_EXTENSIONS],
)

question = picked
attached_files = []
if submitted is not None:
    if isinstance(submitted, str):
        question = submitted
    else:
        question = (submitted.text or "").strip() or None
        attached_files = list(submitted.files or [])

if attached_files:
    with st.spinner("Indexing attached document(s)..."):
        indexed, errors = index_uploaded_files(attached_files)
    note_parts = []
    if indexed:
        note_parts.append("📄 Indexed for this session: " + ", ".join(indexed) + ".")
    if errors:
        note_parts.append("⚠️ Failed: " + "; ".join(errors))
    if not question and indexed:
        note_parts.append("Ask me anything about it!")
    note = " ".join(note_parts)
    st.session_state.messages.append({"role": "assistant", "content": note})
    sync_current_chat()
    if not question:
        st.rerun()

if question:
    if client is None or not index.exists:
        st.stop()
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("SmartCAT is thinking — searching the knowledge base..."):
            result = run_agent(
                question,
                history=[{"role": m["role"], "content": m["content"]}
                         for m in st.session_state.messages[:-1]],
                client=client,
                model=CHAT_MODEL,
                tools=build_tools(),
            )

        def _stream_words(text: str):
            for word in text.split(" "):
                yield word + " "
                time.sleep(0.006)

        st.write_stream(_stream_words(result.answer))

        unique_sources = []
        seen_urls = set()
        for src in result.sources:
            key = src.get("url") or src.get("title")
            if key and key not in seen_urls:
                seen_urls.add(key)
                unique_sources.append(src)
        trace = {"tool_calls": result.tool_calls, "sources": unique_sources}
        if result.tool_calls or unique_sources:
            render_trace(trace)

    log_id = qa_log.log(question, result.answer, result.tool_calls, unique_sources)
    st.session_state.messages.append({
        "role": "assistant", "content": result.answer, "trace": trace, "log_id": log_id,
    })
    sync_current_chat()
    st.rerun()
