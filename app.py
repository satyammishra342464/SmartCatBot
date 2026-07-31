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
import streamlit.components.v1 as components
from dotenv import load_dotenv

from core.loader import SUPPORTED_EXTENSIONS

import service.chat_service as svc
from service.config import get_settings

load_dotenv()

APP_DIR = Path(__file__).resolve().parent

st.set_page_config(page_title="SmartCAT — CAT Modelling Assistant", page_icon="🌀",
                   layout="wide", initial_sidebar_state="expanded")


@st.cache_resource
def _bootstrap() -> dict:
    """Create tables and warm shared resources, once per process."""
    status = {"db": False, "resources": False, "error": None}
    try:
        status.update(svc.init_service())
    except Exception as exc:
        status["error"] = f"Database not reachable: {exc}"
        return status
    try:
        svc.get_resources()
        status["resources"] = True
    except Exception as exc:
        status["error"] = str(exc)
    return status


BOOT = _bootstrap()

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
    pointer-events: none;
}}
/* Hover glow triggered by the transparent popover button above */
[data-testid="stSidebar"]:has([data-testid="stPopover"] button:hover) .sc-account,
[data-testid="stSidebar"]:has([data-testid="stPopover"] button[aria-expanded="true"]) .sc-account {{
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
/* ---------- sc-account extras ---------- */
.sc-acct-dots {{
    margin-left: auto; flex-shrink: 0;
    font-size: 1.05rem; color: {P["MID"]};
    letter-spacing: 3px; line-height: 1; padding-bottom: 2px;
}}
/* Transparent popover button sits ON TOP of the account bar (z-index 1000 > 999).
   It is invisible but fully clickable — no JS delegation needed. */
[data-testid="stSidebar"] [data-testid="stPopover"] > div > button,
[data-testid="stSidebar"] [data-testid="stPopover"] > button {{
    opacity: 0 !important;
    position: fixed !important;
    bottom: 14px !important; left: 14px !important;
    width: 218px !important; height: 52px !important;
    pointer-events: auto !important;
    cursor: pointer !important;
    z-index: 1000 !important;
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
}}

/* ---------- popover body — professional card with theme support ---------- */
[data-testid="stPopoverBody"] {{
    background: {P["CARD"]} !important;
    border: 1px solid {P["BORDER"]} !important;
    box-shadow: 0 -6px 28px rgba(0,0,0,.25), 0 4px 12px rgba(0,0,0,.15) !important;
    border-radius: 14px !important;
    padding: 8px !important;
    min-width: 232px !important;
}}
[data-testid="stPopoverBody"] p {{
    color: {P["TEXT"]} !important;
}}
[data-testid="stPopoverBody"] [data-testid="stCaptionContainer"] p {{
    color: {P["SUB"]} !important;
    font-size: .75rem !important;
}}
[data-testid="stPopoverBody"] hr {{
    border-color: {P["BORDER"]} !important; margin: 6px 0 !important;
}}
[data-testid="stPopoverBody"] a {{
    color: {P["SUB"]} !important;
    text-decoration: none !important;
    font-size: .74rem !important;
    pointer-events: none;
}}
[data-testid="stPopoverBody"] .stButton button {{
    background: transparent !important;
    border: none !important;
    color: {P["TEXT"]} !important;
    text-align: left !important;
    justify-content: flex-start !important;
    font-weight: 400 !important;
    font-size: .88rem !important;
    border-radius: 8px !important;
    padding: 7px 12px !important;
    min-height: unset !important;
    box-shadow: none !important;
    animation: none !important;
    transform: none !important;
    transition: background .15s ease !important;
    width: 100% !important;
}}
[data-testid="stPopoverBody"] .stButton button:hover {{
    background: {P["BTN_HOVER_BG"]} !important;
    transform: none !important; box-shadow: none !important;
    border-color: transparent !important;
}}
[data-testid="stPopoverBody"] [data-testid="stBaseButton-primary"] {{
    background: {EXL_ORANGE} !important;
    color: #FFFFFF !important;
    border-color: {EXL_ORANGE} !important;
}}
[data-testid="stPopoverBody"] [data-testid="stBaseButton-primary"]:hover {{
    background: {EXL_ORANGE_DARK} !important;
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

/* ---------- @st.dialog modal — dark mode ---------- */
[data-testid="stDialog"] {{
    background: rgba(0,0,0,.60) !important;
}}
[data-testid="stDialog"] > div {{
    background: {P["CARD"]} !important;
    border: 1px solid {P["BORDER"]} !important;
    border-radius: 16px !important;
    box-shadow: 0 12px 48px rgba(0,0,0,.70) !important;
}}
[data-testid="stDialog"] h1, [data-testid="stDialog"] h2,
[data-testid="stDialog"] h3, [data-testid="stDialog"] h4,
[data-testid="stDialog"] h5, [data-testid="stDialog"] h6 {{
    color: {P["TEXT"]} !important;
}}
[data-testid="stDialog"] p {{
    color: {P["TEXT"]} !important;
}}
[data-testid="stDialog"] [data-testid="stMarkdownContainer"] p,
[data-testid="stDialog"] [data-testid="stMarkdownContainer"] li {{
    color: {P["TEXT"]} !important;
}}
[data-testid="stDialog"] [data-testid="stWidgetLabel"] p,
[data-testid="stDialog"] label {{ color: {P["TEXT"]} !important; }}
[data-testid="stDialog"] [data-testid="stCaptionContainer"] p {{
    color: {P["SUB"]} !important;
}}
[data-testid="stDialog"] hr {{ border-color: {P["BORDER"]} !important; }}
/* Text / password inputs */
[data-testid="stDialog"] input[type="text"],
[data-testid="stDialog"] input[type="email"],
[data-testid="stDialog"] input[type="password"],
[data-testid="stDialog"] textarea {{
    background: {P["INPUT_BG"]} !important;
    color: {P["TEXT"]} !important;
    border-color: {P["BORDER"]} !important;
    color-scheme: dark;
}}
/* Input wrapper — Streamlit uses stTextInputRootElement (not BaseWeb) */
[data-testid="stDialog"] [data-testid="stTextInputRootElement"] {{
    background: {P["INPUT_BG"]} !important;
    border-color: {P["BORDER"]} !important;
    border-radius: 8px !important;
}}
[data-testid="stDialog"] [data-testid="stTextInputRootElement"]:has(input:disabled) {{
    background: rgba(255,255,255,.05) !important;
    border-color: {P["BORDER"]} !important;
}}
[data-testid="stDialog"] input:disabled,
[data-testid="stDialog"] textarea:disabled {{
    background: transparent !important;
    color: {P["MID"]} !important;
    -webkit-text-fill-color: {P["MID"]} !important;
    opacity: 1 !important;
}}
/* Selectbox trigger */
[data-testid="stDialog"] [data-testid="stSelectbox"] > div > div,
[data-testid="stDialog"] [data-baseweb="select"] > div {{
    background: {P["INPUT_BG"]} !important;
    color: {P["TEXT"]} !important;
    border-color: {P["BORDER"]} !important;
}}
[data-testid="stDialog"] [data-baseweb="select"] span {{
    color: {P["TEXT"]} !important;
}}
/* Selectbox virtual dropdown — renders in a portal OUTSIDE stDialog, must be global */
[data-testid="stSelectboxVirtualDropdown"] {{
    background: {P["CARD"]} !important;
    border: 1px solid {P["BORDER"]} !important;
    border-radius: 10px !important;
    box-shadow: 0 8px 28px rgba(0,0,0,.50) !important;
}}
[data-testid="stSelectboxVirtualDropdown"] [role="option"],
[data-testid="stSelectboxVirtualDropdown"] [role="listbox"] > div {{
    background: {P["CARD"]} !important;
    color: {P["TEXT"]} !important;
}}
[data-testid="stSelectboxVirtualDropdown"] [role="option"]:hover,
[data-testid="stSelectboxVirtualDropdown"] [aria-selected="true"] {{
    background: {P["BTN_HOVER_BG"]} !important;
    color: {P["TEXT"]} !important;
}}
/* Also keep BaseWeb selectors for forward compatibility */
[data-baseweb="popover"] ul[role="listbox"],
[data-baseweb="menu"] {{
    background: {P["CARD"]} !important;
    border: 1px solid {P["BORDER"]} !important;
    border-radius: 10px !important;
    box-shadow: 0 8px 28px rgba(0,0,0,.50) !important;
}}
[data-baseweb="menu"] li,
[data-baseweb="menu"] [role="option"] {{
    background: {P["CARD"]} !important;
    color: {P["TEXT"]} !important;
}}
[data-baseweb="menu"] li:hover,
[data-baseweb="menu"] [aria-selected="true"] {{
    background: {P["BTN_HOVER_BG"]} !important;
    color: {P["TEXT"]} !important;
}}
/* Radio buttons */
[data-testid="stDialog"] [data-testid="stRadio"] label {{ color: {P["TEXT"]} !important; }}
[data-testid="stDialog"] [data-testid="stRadio"] p {{ color: {P["TEXT"]} !important; }}
/* Buttons */
[data-testid="stDialog"] .stButton button {{
    background: {P["BTN_BG"]} !important;
    color: {P["BTN_TEXT"]} !important;
    border-color: rgba(232, 78, 14, .45) !important;
}}
[data-testid="stDialog"] .stButton button:hover {{
    background: {P["BTN_HOVER_BG"]} !important;
    border-color: {EXL_ORANGE} !important;
}}
[data-testid="stDialog"] [data-testid="stBaseButton-primary"] {{
    background: {EXL_ORANGE} !important;
    color: #FFFFFF !important;
    border-color: {EXL_ORANGE} !important;
}}
[data-testid="stDialog"] [data-testid="stBaseButton-primary"]:hover {{
    background: {EXL_ORANGE_DARK} !important;
}}
/* Info / success / warning alert boxes */
[data-testid="stDialog"] [data-testid="stInfo"],
[data-testid="stDialog"] [data-testid="stAlert"] {{
    background: rgba(80,140,255,.12) !important;
    border-color: rgba(80,140,255,.35) !important;
    color: {P["TEXT"]} !important;
}}
[data-testid="stDialog"] [data-testid="stInfo"] p,
[data-testid="stDialog"] [data-testid="stAlert"] p {{
    color: {P["TEXT"]} !important;
}}
[data-testid="stDialog"] [data-testid="stSuccess"] {{
    background: rgba(34,197,94,.12) !important;
    border-color: rgba(34,197,94,.35) !important;
}}
[data-testid="stDialog"] [data-testid="stError"] {{
    background: rgba(229,72,77,.12) !important;
    border-color: rgba(229,72,77,.35) !important;
}}
/* Bordered containers (Upgrade plan cards) */
[data-testid="stDialog"] [data-testid="stVerticalBlockBorderWrapper"] > div {{
    background: rgba(255,255,255,.04) !important;
    border-color: {P["BORDER"]} !important;
}}
/* Close (X) button */
[data-testid="stDialog"] button[aria-label="Close"],
[data-testid="stDialog"] button[kind="header"] {{
    color: {P["TEXT"]} !important;
    background: transparent !important;
}}
/* "Forgotten password?" — plain text link, no button chrome */
[data-testid="stTabsContainer"] button[kind="secondary"],
[data-testid="stTabsContainer"] [data-testid="stBaseButton-secondary"] > button {{
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    color: {P["SUB"]} !important;
    font-weight: 600 !important;
    font-size: .88rem !important;
    padding: 4px 8px !important;
    min-height: 0 !important;
    width: auto !important;
    cursor: pointer !important;
}}
[data-testid="stTabsContainer"] button[kind="secondary"]:hover,
[data-testid="stTabsContainer"] [data-testid="stBaseButton-secondary"] > button:hover {{
    background: transparent !important;
    color: {EXL_ORANGE} !important;
    border: none !important;
    box-shadow: none !important;
}}
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


# ------------------------------------------------------------------ session persistence
# Token → user dict; @st.cache_resource survives reruns (not server restarts).
# The URL ?s=<token> survives browser refresh; localStorage covers new tabs.

@st.cache_resource
def _token_store() -> dict:
    return {}

def _make_token(user: dict) -> str:
    tok = uuid.uuid4().hex
    _token_store()[tok] = user
    return tok

def _load_token(tok: str) -> dict | None:
    return _token_store().get(tok)

def _drop_token(tok: str) -> None:
    _token_store().pop(tok, None)


def _safe_prefs() -> dict:
    uid = st.session_state.get("auth_user", {}).get("id", "")
    if not uid:
        return {}
    try:
        return svc.get_prefs(uid)
    except Exception:
        return {}


def _on_dark_toggle() -> None:
    st.session_state.dark_pref = st.session_state.dark_widget
    uid = st.session_state.get("auth_user", {}).get("id", "")
    if uid:
        try:
            svc.set_prefs(uid, {"dark_mode": st.session_state.dark_pref})
        except Exception:
            pass


if "dark_pref" not in st.session_state:
    st.session_state.dark_pref = bool(_safe_prefs().get("dark_mode", False))

DARK_MODE = st.session_state.dark_pref
st.markdown(build_css(DARK_MODE), unsafe_allow_html=True)

# ------------------------------------------------------------------ forgot-password dialog


@st.dialog("Reset Password")
def _dialog_forgot_password():
    st.markdown(
        '<p style="font-size:.85rem;opacity:.7;margin-bottom:4px">'
        'Enter your registered email and create a new password.</p>',
        unsafe_allow_html=True,
    )
    with st.form("forgot_form", border=False):
        fp_email = st.text_input("Enter your Registered Email",
                                 placeholder="you@example.com")
        fp_pw    = st.text_input("Create New Password", type="password",
                                 help="Minimum 6 characters")
        fp_pw2   = st.text_input("Confirm New Password", type="password")
        fp_btn   = st.form_submit_button("Reset Password",
                                         use_container_width=True, type="primary")
    if fp_btn:
        if not fp_email or not fp_pw:
            st.error("Please fill in all fields.")
        elif fp_pw != fp_pw2:
            st.error("Passwords don't match.")
        elif len(fp_pw) < 6:
            st.error("Password must be at least 6 characters.")
        else:
            if svc.reset_password(fp_email, fp_pw):
                st.success("Password reset! You can now log in with your new password.")
            else:
                st.error("No account found with that email address.")


# ------------------------------------------------------------------ auth gate


def _show_auth_page() -> None:
    """Login / Sign-up page. Sets st.session_state.auth_user on success."""
    if st.session_state.pop("_clear_ls", False):
        # User just logged out — wipe the localStorage token
        components.html("<script>localStorage.removeItem('sc_s');</script>", height=0)
    else:
        # Try to restore from localStorage (covers new browser tabs)
        components.html("""<script>
(function(){
  var t = localStorage.getItem('sc_s');
  if (t) {
    var u = new URL(window.parent.location.href);
    if (!u.searchParams.get('s')) {
      u.searchParams.set('s', t);
      window.parent.location.replace(u.toString());
    }
  }
})();
</script>""", height=0)
    _, col, _ = st.columns([1, 1.4, 1])
    with col:
        st.markdown(
            f'<div style="text-align:center;padding:20px 0 28px">'
            f'{logo(72, "auth")}'
            f'<div class="sc-title" style="font-size:1.9rem;margin-top:14px">SmartCAT</div>'
            f'<div class="sc-sub">CAT Modelling Assistant — Please sign in</div></div>',
            unsafe_allow_html=True,
        )
        if BOOT.get("error"):
            st.error(BOOT["error"])

        tab_login, tab_signup, tab_admin = st.tabs(["🔐  Login", "✨  Sign Up", "🛡️  Admin"])

        with tab_login:
            with st.form("login_form", border=False):
                email = st.text_input("Email", placeholder="you@example.com")
                password = st.text_input("Password", type="password")
                login_btn = st.form_submit_button(
                    "Login", use_container_width=True, type="primary")
            if login_btn:
                if not email or not password:
                    st.error("Please fill in all fields.")
                else:
                    res = svc.auth_login(email, password)
                    if res:
                        _tok = _make_token(res)
                        st.session_state.auth_user = res
                        st.session_state._save_ls = _tok
                        st.query_params["s"] = _tok
                        st.rerun()
                    else:
                        st.error("Invalid email or password.")
            # Centred plain-text link (button chrome stripped via CSS above)
            _fc1, _fc2, _fc3 = st.columns([2, 1.5, 2])
            with _fc2:
                if st.button("Forgotten password?", key="btn_forgot"):
                    _dialog_forgot_password()

        with tab_admin:
            with st.form("admin_form", border=False):
                adm_email = st.text_input("Admin Email", placeholder="admin@example.com", key="adm_email")
                adm_pw    = st.text_input("Admin Password", type="password", key="adm_pw")
                adm_btn   = st.form_submit_button("Login as Admin", use_container_width=True, type="primary")
            if adm_btn:
                _ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "satyam.mishra2@exlservice.com")
                _ADMIN_PW    = os.getenv("ADMIN_PASSWORD", "smartcat@admin123")
                if adm_email == _ADMIN_EMAIL and adm_pw == _ADMIN_PW:
                    st.session_state.admin_logged_in = True
                    st.rerun()
                else:
                    st.error("Invalid admin credentials.")

        with tab_signup:
            with st.form("signup_form", border=False):
                su_name = st.text_input("Full Name", placeholder="Your Name")
                su_email = st.text_input("Email", placeholder="you@example.com",
                                         key="su_email")
                su_pw = st.text_input("Password", type="password", key="su_pw",
                                      help="Minimum 6 characters")
                su_pw2 = st.text_input("Confirm Password", type="password", key="su_pw2")
                signup_btn = st.form_submit_button(
                    "Create Account", use_container_width=True, type="primary")
            if signup_btn:
                if not su_name.strip() or not su_email or not su_pw:
                    st.error("Please fill in all fields.")
                elif su_pw != su_pw2:
                    st.error("Passwords don't match.")
                elif len(su_pw) < 6:
                    st.error("Password must be at least 6 characters.")
                else:
                    res = svc.auth_register(su_name, su_email, su_pw)
                    if res:
                        _tok = _make_token(res)
                        st.session_state.auth_user = res
                        st.session_state._save_ls = _tok
                        st.query_params["s"] = _tok
                        st.rerun()
                    else:
                        st.error("This email is already registered — please log in.")


# ------------------------------------------------------------------ admin dashboard
def _show_admin_dashboard():
    import numpy as np
    import pandas as pd
    import plotly.express as px
    from sklearn.cluster import KMeans
    from sqlalchemy import create_engine, text as sql_text

    st.set_page_config(page_title="SmartCAT Admin", page_icon="🛡️", layout="wide") if False else None

    cfg = get_settings()

    # Header
    st.markdown(
        '<h1 style="margin-bottom:0">🛡️ SmartCAT Admin Dashboard</h1>'
        '<p style="opacity:.6;margin-top:4px">Question topic analytics — who is asking what</p>',
        unsafe_allow_html=True,
    )

    col_ref, col_out = st.columns([6, 1])
    with col_out:
        if st.button("🚪 Logout", type="secondary"):
            st.session_state.admin_logged_in = False
            st.rerun()
    with col_ref:
        if st.button("🔄 Refresh Data"):
            st.cache_data.clear()
            st.rerun()

    st.divider()

    # ── Load data from Neon ──────────────────────────────────────────
    @st.cache_data(ttl=300)
    def _load_qa():
        engine = create_engine(cfg.database_url)
        with engine.connect() as conn:
            df = pd.read_sql(
                sql_text("SELECT id, user_id, ts, question FROM qa_log ORDER BY ts DESC"),
                conn,
            )
        df["ts"]   = pd.to_datetime(df["ts"])
        df["date"] = df["ts"].dt.date
        return df

    @st.cache_data(ttl=3600, show_spinner=False)
    def _embed_qs(qs: tuple) -> np.ndarray:
        import core  # truststore
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=cfg.api_key)
        vecs, batch = [], 50
        for i in range(0, len(qs), batch):
            chunk = list(qs[i:i+batch])
            resp = client.models.embed_content(
                model=cfg.gemini_embed_model,
                contents=[types.Content(parts=[types.Part.from_text(text=q)]) for q in chunk],
                config=types.EmbedContentConfig(task_type="CLUSTERING"),
            )
            vecs.extend(list(e.values) for e in resp.embeddings)
        return np.array(vecs)

    @st.cache_data(ttl=3600, show_spinner=False)
    def _label_cluster(sample: tuple) -> str:
        import core
        from google import genai
        client = genai.Client(api_key=cfg.api_key)
        qs = "\n".join(f"- {q}" for q in sample[:8])
        resp = client.models.generate_content(
            model=cfg.gemini_model,
            contents=(
                f"These are questions from an insurance CAT modelling chatbot:\n{qs}\n\n"
                "Give a short topic label (2-4 words). Reply with ONLY the label."
            ),
        )
        return resp.text.strip()

    @st.cache_data(ttl=3600)
    def _cluster(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        k = min(6, len(df))
        qs = tuple(df["question"].tolist())
        with st.spinner("Analysing question topics…"):
            vecs = _embed_qs(qs)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        vecs_n = vecs / np.where(norms == 0, 1, norms)
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        df = df.copy()
        df["cluster_id"] = km.fit_predict(vecs_n)
        labels = {}
        for cid in range(k):
            sample = tuple(df[df["cluster_id"] == cid]["question"].tolist()[:8])
            labels[cid] = _label_cluster(sample)
        df["topic"] = df["cluster_id"].map(labels)
        return df

    df_raw = _load_qa()
    if df_raw.empty:
        st.warning("No questions in qa_log yet.")
        return

    df = _cluster(df_raw)

    # ── Filters ─────────────────────────────────────────────────────
    f1, f2, f3 = st.columns(3)
    with f1:
        users  = ["All Users"]  + sorted(df["user_id"].dropna().unique().tolist())
        sel_u  = st.selectbox("👤 User", users)
    with f2:
        topics = ["All Topics"] + sorted(df["topic"].unique().tolist())
        sel_t  = st.selectbox("🏷️ Topic", topics)
    with f3:
        dates = sorted(df["date"].unique())
        dr = st.date_input("📅 Date Range", value=(dates[0], dates[-1]) if len(dates) >= 2 else (dates[0], dates[0]))

    dff = df.copy()
    if sel_u != "All Users":  dff = dff[dff["user_id"] == sel_u]
    if sel_t != "All Topics": dff = dff[dff["topic"]   == sel_t]
    if dr and len(dr) == 2:
        dff = dff[(dff["date"] >= dr[0]) & (dff["date"] <= dr[1])]

    # ── KPI cards ───────────────────────────────────────────────────
    st.divider()
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("📨 Total Questions",  len(dff))
    k2.metric("👥 Unique Users",     dff["user_id"].nunique())
    k3.metric("🏷️ Topics Found",     dff["topic"].nunique())
    k4.metric("🏆 Most Active User", dff["user_id"].value_counts().idxmax() if not dff.empty else "—")

    st.divider()

    # ── Charts row 1 ────────────────────────────────────────────────
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("📊 Questions by Topic")
        tc = dff.groupby("topic").size().reset_index(name="count").sort_values("count", ascending=False)
        fig1 = px.bar(tc, x="topic", y="count", color="topic",
                      color_discrete_sequence=px.colors.qualitative.Set2,
                      labels={"topic": "Topic", "count": "Questions"})
        fig1.update_layout(showlegend=False, xaxis_tickangle=-30, margin=dict(t=10))
        st.plotly_chart(fig1, use_container_width=True)

    with c2:
        st.subheader("👤 Questions per User")
        uc = dff.groupby("user_id").size().reset_index(name="count").sort_values("count", ascending=False).head(10)
        fig2 = px.bar(uc, x="user_id", y="count", color="user_id",
                      color_discrete_sequence=px.colors.qualitative.Pastel,
                      labels={"user_id": "User", "count": "Questions"})
        fig2.update_layout(showlegend=False, xaxis_tickangle=-30, margin=dict(t=10))
        st.plotly_chart(fig2, use_container_width=True)

    # ── Heatmap ──────────────────────────────────────────────────────
    st.subheader("🔥 User × Topic Heatmap")
    heat = dff.groupby(["user_id", "topic"]).size().reset_index(name="count")
    if not heat.empty:
        pivot = heat.pivot(index="user_id", columns="topic", values="count").fillna(0)
        fig3  = px.imshow(pivot, aspect="auto", color_continuous_scale="Blues",
                          labels=dict(x="Topic", y="User", color="Questions"), text_auto=True)
        fig3.update_layout(height=max(300, len(pivot) * 45), margin=dict(t=10))
        st.plotly_chart(fig3, use_container_width=True)

    # ── Stacked bar — per user topic breakdown ───────────────────────
    st.subheader("🔍 Per-User Topic Breakdown")
    ut = dff.groupby(["user_id", "topic"]).size().reset_index(name="count")
    if not ut.empty:
        fig4 = px.bar(ut, x="user_id", y="count", color="topic", barmode="stack",
                      color_discrete_sequence=px.colors.qualitative.Vivid,
                      labels={"user_id": "User", "count": "Questions", "topic": "Topic"})
        fig4.update_layout(xaxis_tickangle=-30, margin=dict(t=10))
        st.plotly_chart(fig4, use_container_width=True)

    # ── Timeline ─────────────────────────────────────────────────────
    st.subheader("📅 Questions Over Time")
    tl = dff.groupby(["date", "topic"]).size().reset_index(name="count")
    if not tl.empty:
        fig5 = px.line(tl, x="date", y="count", color="topic", markers=True,
                       color_discrete_sequence=px.colors.qualitative.Set1,
                       labels={"date": "Date", "count": "Questions", "topic": "Topic"})
        fig5.update_layout(margin=dict(t=10))
        st.plotly_chart(fig5, use_container_width=True)

    # ── Raw log ──────────────────────────────────────────────────────
    st.divider()
    st.subheader("📋 Full Question Log")
    st.dataframe(
        dff[["ts", "user_id", "topic", "question"]].sort_values("ts", ascending=False).reset_index(drop=True),
        use_container_width=True, height=320,
    )


# Restore session from URL token (survives browser refresh)
if st.session_state.get("auth_user") is None:
    _qt = st.query_params.get("s")
    if _qt:
        _restored = _load_token(_qt)
        if _restored:
            st.session_state.auth_user = _restored

if st.session_state.get("admin_logged_in"):
    _show_admin_dashboard()
    st.stop()

if st.session_state.get("auth_user") is None:
    _show_auth_page()
    st.stop()

# Save token to localStorage after first login (so new tabs can restore it)
_ls_tok = st.session_state.pop("_save_ls", None)
if _ls_tok:
    components.html(
        f"<script>localStorage.setItem('sc_s',{json.dumps(_ls_tok)});</script>",
        height=0,
    )

# Logged in — derive identity from session
_au = st.session_state.auth_user
USER_ID = _au["id"]
USER_NAME = _au.get("name") or _au["id"]
USER_EMAIL = _au["email"]

# ------------------------------------------------------------------ resources


def _get_resources():
    """Shared Gemini client + knowledge index from the service layer (a process
    singleton). Returns (None, None) if the backend/API key isn't available."""
    try:
        res = svc.get_resources()
        return res.client, res.index
    except Exception:
        return None, None


client, index = _get_resources()


def sync_current_chat() -> None:
    """Persist the active conversation (creates it on first message). Now writes
    just this chat to Postgres via the service, scoped to the current user."""
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
        chat = None
        for c in st.session_state.chats:
            if c["id"] == st.session_state.current_chat_id:
                c["messages"] = messages
                c["ts"] = time.time()
                chat = c
                break
        if chat is None:
            return
    try:
        svc.save_chat(USER_ID, chat, name=USER_NAME, email=USER_EMAIL or None)
    except Exception as exc:
        st.warning(f"Could not save chat: {exc}")


if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_id" not in st.session_state:
    st.session_state.session_id = uuid.uuid4().hex[:12]  # per-browser-session uploads
if "chats" not in st.session_state:
    try:
        st.session_state.chats = svc.list_chats(USER_ID)
    except Exception:
        st.session_state.chats = []
if "current_chat_id" not in st.session_state:
    st.session_state.current_chat_id = None
if "pending_delete_chat_id" not in st.session_state:
    st.session_state.pending_delete_chat_id = None


def index_uploaded_files(files) -> tuple[list[str], list[str]]:
    """Persist + embed uploaded files for this session via the service layer."""
    payload = [(f.name, bytes(f.getbuffer())) for f in files]
    return svc.upload(USER_ID, st.session_state.session_id, payload)


# ------------------------------------------------------------------ dialogs

@st.dialog("Account Settings")
def _dialog_account():
    au = st.session_state.auth_user
    st.markdown("#### Profile")
    new_name = st.text_input("Full Name", value=au.get("name", ""), key="dlg_acc_name")
    st.text_input("Email", value=au.get("email", ""), disabled=True, key="dlg_acc_email",
                  help="Email cannot be changed")
    st.divider()
    st.markdown("#### Change Password")
    old_pw = st.text_input("Current Password", type="password", key="dlg_acc_oldpw")
    new_pw = st.text_input("New Password", type="password", key="dlg_acc_newpw")
    new_pw2 = st.text_input("Confirm New Password", type="password", key="dlg_acc_newpw2")
    col1, col2 = st.columns(2)
    if col1.button("Save Changes", type="primary", use_container_width=True):
        errors: list[str] = []
        changed = False
        if new_name.strip() and new_name.strip() != au.get("name", ""):
            try:
                svc.update_user_name(au["id"], new_name.strip())
                st.session_state.auth_user["name"] = new_name.strip()
                changed = True
            except Exception as exc:
                errors.append(f"Could not update name: {exc}")
        if old_pw or new_pw:
            if not old_pw:
                errors.append("Enter your current password.")
            elif not new_pw:
                errors.append("Enter a new password.")
            elif new_pw != new_pw2:
                errors.append("New passwords don't match.")
            elif len(new_pw) < 6:
                errors.append("Password must be at least 6 characters.")
            else:
                try:
                    if svc.change_password(au["id"], old_pw, new_pw):
                        changed = True
                    else:
                        errors.append("Current password is incorrect.")
                except Exception as exc:
                    errors.append(f"Password update failed: {exc}")
        for e in errors:
            st.error(e)
        if changed and not errors:
            st.success("Changes saved! Click Close to continue.")
    if col2.button("Close", use_container_width=True):
        st.rerun()


@st.dialog("Language")
def _dialog_language():
    LANGS = ["English", "Hindi", "Spanish", "French", "German",
             "Arabic", "Japanese", "Chinese (Simplified)"]
    try:
        prefs = svc.get_prefs(USER_ID)
    except Exception:
        prefs = {}
    cur = prefs.get("language", "English")
    idx = LANGS.index(cur) if cur in LANGS else 0
    selected = st.selectbox("Interface Language", LANGS, index=idx)
    st.info("ℹ️ Multi-language support is coming soon. Your selection will be saved.")
    col1, col2 = st.columns(2)
    if col1.button("Save", type="primary", use_container_width=True):
        try:
            svc.set_prefs(USER_ID, {**prefs, "language": selected})
            st.success(f"Language set to {selected}. Click Close to continue.")
        except Exception as exc:
            st.error(str(exc))
    if col2.button("Close", use_container_width=True):
        st.rerun()


@st.dialog("Appearance")
def _dialog_appearance():
    cur_label = "Dark" if st.session_state.dark_pref else "Light"
    theme = st.radio("Theme", ["Light", "Dark"],
                     index=0 if cur_label == "Light" else 1, horizontal=True)
    st.caption("Click Apply to switch the theme immediately.")
    col1, col2 = st.columns(2)
    if col1.button("Apply", type="primary", use_container_width=True):
        st.session_state.dark_pref = (theme == "Dark")
        try:
            prefs = svc.get_prefs(USER_ID)
            svc.set_prefs(USER_ID, {**prefs, "dark_mode": st.session_state.dark_pref})
        except Exception:
            pass
        st.rerun()
    if col2.button("Close", use_container_width=True):
        st.rerun()


@st.dialog("Upgrade Plan")
def _dialog_upgrade():
    if st.session_state.get("_upgrade_show_card"):
        st.markdown("#### Add Payment Method")
        st.text_input("Card Number", placeholder="1234 5678 9012 3456", key="dlg_cardno")
        c1, c2 = st.columns(2)
        c1.text_input("Expiry (MM/YY)", placeholder="12/27", key="dlg_exp")
        c2.text_input("CVV", placeholder="123", type="password", key="dlg_cvv")
        st.text_input("Name on Card", placeholder="Your Name", key="dlg_cardname")
        st.warning("🚧 Pro Plan is currently **under development**. "
                   "Your card will **not** be charged.")
        bc1, bc2 = st.columns(2)
        bc1.button("Subscribe Now", type="primary", use_container_width=True, disabled=True)
        if bc2.button("← Back", use_container_width=True):
            st.session_state._upgrade_show_card = False
            st.rerun()
        return

    col_b, col_p = st.columns(2)
    with col_b:
        with st.container(border=True):
            st.markdown("#### 🆓 Basic")
            st.markdown("**Free**")
            st.markdown("""
- ✓ 50 questions / day
- ✓ Knowledge base search
- ✓ Web search
- ✓ Document upload (5 MB)
- ✓ Chat history (30 days)
""")
            st.button("Current Plan ✓", disabled=True, use_container_width=True,
                      key="dlg_basic_btn")
    with col_p:
        with st.container(border=True):
            st.markdown("#### ⭐ Pro")
            st.markdown("**$10 / month**")
            st.markdown("""
- ✓ Unlimited questions
- ✓ Get more limit
- ✓ Priority response
- ✓ Document upload (50 MB)
- ✓ Unlimited chat history
- ✓ API access
""")
            if st.button("Upgrade to Pro →", type="primary",
                         use_container_width=True, key="dlg_pro_btn"):
                st.session_state._upgrade_show_card = True
                st.rerun()
    st.caption("🚧 Pro Plan is currently under development — stay tuned!")
    if st.button("Close", use_container_width=True, key="dlg_upgrade_close"):
        st.rerun()


# ----------------------------------------------------------------- dialog triggers
_dlg = st.session_state.pop("open_dialog", None)
if _dlg == "account":
    _dialog_account()
elif _dlg == "language":
    _dialog_language()
elif _dlg == "appearance":
    _dialog_appearance()
elif _dlg == "upgrade":
    st.session_state._upgrade_show_card = False
    _dialog_upgrade()


# ------------------------------------------------------------------ sidebar

with st.sidebar:
    st.markdown(
        f'<div class="sc-header">{logo(46, "sb")}'
        f'<div><div class="sc-title" style="font-size:1.6rem">SmartCAT</div>'
        f'<div class="sc-sub">CAT Modelling Assistant</div></div></div>',
        unsafe_allow_html=True,
    )
    if BOOT.get("error"):
        st.error(BOOT["error"])
    if client is None:
        st.error("GEMINI_API_KEY missing in .env")
    elif index is None or not index.exists:
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
            pending = st.session_state.pending_delete_chat_id == chat["id"]
            if pending:
                col_lbl, col_confirm, col_cancel = st.columns([3, 3, 1])
                col_lbl.caption((chat["title"][:22] + "…") if len(chat["title"]) > 22
                                else chat["title"])
                if col_confirm.button("Delete it?", key=f"confirm-del-{chat['id']}",
                                      type="primary", use_container_width=True):
                    st.session_state.chats = [c for c in st.session_state.chats
                                              if c["id"] != chat["id"]]
                    st.session_state.pending_delete_chat_id = None
                    if is_current:
                        st.session_state.messages = []
                        st.session_state.current_chat_id = None
                    try:
                        svc.delete_chat(USER_ID, chat["id"])
                    except Exception:
                        pass
                    st.rerun()
                if col_cancel.button("✕", key=f"cancel-del-{chat['id']}"):
                    st.session_state.pending_delete_chat_id = None
                    st.rerun()
            else:
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
                if col_del.button("🗑", key=f"del-{chat['id']}"):
                    st.session_state.pending_delete_chat_id = chat["id"]
                    st.rerun()

    try:
        session_docs = svc.session_documents(USER_ID, st.session_state.session_id)
    except Exception:
        session_docs = {}
    if session_docs:
        st.divider()
        st.caption("📄 Attached this session: " + ", ".join(session_docs))

    # ── fixed bottom-left account bar + popover menu ──────────────────────────
    initials = "".join(word[0] for word in USER_NAME.split()[:2]).upper() or "U"
    _em = USER_EMAIL if len(USER_EMAIL) <= 24 else USER_EMAIL[:10] + "…" + USER_EMAIL[-10:]
    # Pretty HTML account bar (ChatGPT-style, fixed bottom-left)
    # Script uses document.body event-delegation so it survives Streamlit rerenders.
    # Guard with window._scAcctDel so duplicate listeners are never added.
    st.markdown(
        f'<div class="sc-account">'
        f'<div class="sc-avatar">{html_lib.escape(initials)}</div>'
        f'<div class="sc-account-info">'
        f'<span class="sc-account-name">{html_lib.escape(USER_NAME)}</span>'
        f'<span class="sc-account-mail">{html_lib.escape(_em)}</span>'
        f'</div>'
        f'<span class="sc-acct-dots">···</span>'
        f'</div>',
        unsafe_allow_html=True,
    )
    # The actual Streamlit popover — hidden by CSS, triggered by the bar's onclick
    with st.popover("⠀", use_container_width=False):
        st.markdown(f"**{html_lib.escape(USER_NAME)}**")
        _sub_color = theme_palette(DARK_MODE)["SUB"]
        st.markdown(
            f'<span style="font-size:.74rem;color:{_sub_color};display:block;margin:-6px 0 2px;word-break:break-all">'
            f'{html_lib.escape(USER_EMAIL)}</span>',
            unsafe_allow_html=True,
        )
        st.divider()
        if st.button("⚙️  Account Settings", use_container_width=True,
                     key="menu_account"):
            st.session_state.open_dialog = "account"
            st.rerun()
        if st.button("🌐  Language", use_container_width=True, key="menu_lang"):
            st.session_state.open_dialog = "language"
            st.rerun()
        if st.button("🎨  Appearance", use_container_width=True, key="menu_appear"):
            st.session_state.open_dialog = "appearance"
            st.rerun()
        if st.button("⭐  Upgrade Plan", use_container_width=True, key="menu_upgrade"):
            st.session_state.open_dialog = "upgrade"
            st.rerun()
        st.divider()
        if st.button("🚪  Logout", use_container_width=True, key="menu_logout",
                     type="primary"):
            _old_tok = st.query_params.get("s")
            if _old_tok:
                _drop_token(_old_tok)
            try:
                st.query_params.clear()
            except Exception:
                pass
            del st.session_state.auth_user
            for _k in ["messages", "chats", "current_chat_id", "session_id",
                        "dark_pref", "pending_delete_chat_id"]:
                st.session_state.pop(_k, None)
            st.session_state["_clear_ls"] = True
            st.rerun()

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
        svc.feedback(USER_ID, log_id, 1)
        message["feedback"] = 1
        sync_current_chat()
        st.rerun()
    if col_down.button("👎", key=f"down-{st.session_state.current_chat_id}-{i}"):
        svc.feedback(USER_ID, log_id, -1)
        message["feedback"] = -1
        sync_current_chat()
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
    if client is None or index is None or not index.exists:
        st.stop()
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("SmartCAT is thinking — searching the knowledge base..."):
            result = svc.chat(
                USER_ID,
                st.session_state.session_id,
                question,
                history=[{"role": m["role"], "content": m["content"]}
                         for m in st.session_state.messages[:-1]],
            )

        def _stream_words(text: str):
            for word in text.split(" "):
                yield word + " "
                time.sleep(0.006)

        st.write_stream(_stream_words(result["answer"]))

        # Sources are already deduped and the Q&A logged inside the service layer.
        trace = {"tool_calls": result["tool_calls"], "sources": result["sources"]}
        if result["tool_calls"] or result["sources"]:
            render_trace(trace)

    st.session_state.messages.append({
        "role": "assistant", "content": result["answer"], "trace": trace,
        "log_id": result["log_id"],
    })
    sync_current_chat()
    st.rerun()
