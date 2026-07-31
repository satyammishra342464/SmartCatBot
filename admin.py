"""SmartCAT Admin Dashboard — Question Topic Analysis per User."""
import os

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv
from sklearn.cluster import KMeans
from sqlalchemy import create_engine, text

load_dotenv()

# ──────────────────────────── config ────────────────────────────
st.set_page_config(page_title="SmartCAT Admin", page_icon="🛡️", layout="wide")

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "smartcat@admin123")
DATABASE_URL   = os.getenv("DATABASE_URL", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
EMBED_MODEL    = os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-2")
CHAT_MODEL     = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
N_CLUSTERS     = 6

# ──────────────────────────── auth ──────────────────────────────
def _auth():
    if st.session_state.get("admin_ok"):
        return True
    st.markdown("## 🛡️ SmartCAT Admin Login")
    pwd = st.text_input("Password", type="password", placeholder="Enter admin password")
    if st.button("Login", type="primary"):
        if pwd == ADMIN_PASSWORD:
            st.session_state.admin_ok = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    return False

if not _auth():
    st.stop()

# ──────────────────────────── db ────────────────────────────────
@st.cache_resource
def _engine():
    return create_engine(DATABASE_URL)

@st.cache_data(ttl=300)
def load_qa_log() -> pd.DataFrame:
    with _engine().connect() as conn:
        df = pd.read_sql(
            text("SELECT id, user_id, ts, question FROM qa_log ORDER BY ts DESC"),
            conn,
        )
    df["ts"] = pd.to_datetime(df["ts"])
    df["date"] = df["ts"].dt.date
    return df

# ──────────────────────────── embeddings ────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def _embed(questions: tuple[str, ...]) -> np.ndarray:
    import core  # truststore — must import before genai
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GEMINI_API_KEY)
    vecs, batch = [], 50
    for i in range(0, len(questions), batch):
        chunk = list(questions[i : i + batch])
        resp = client.models.embed_content(
            model=EMBED_MODEL,
            contents=[
                types.Content(parts=[types.Part.from_text(text=q)]) for q in chunk
            ],
            config=types.EmbedContentConfig(task_type="CLUSTERING"),
        )
        vecs.extend(list(e.values) for e in resp.embeddings)
    return np.array(vecs)

@st.cache_data(ttl=3600, show_spinner=False)
def _label(sample: tuple[str, ...]) -> str:
    import core
    from google import genai

    client = genai.Client(api_key=GEMINI_API_KEY)
    qs = "\n".join(f"- {q}" for q in sample[:8])
    resp = client.models.generate_content(
        model=CHAT_MODEL,
        contents=(
            f"These questions are from an insurance CAT modelling chatbot:\n{qs}\n\n"
            "Give a short topic label (2-4 words) that best describes these questions. "
            "Reply with ONLY the label."
        ),
    )
    return resp.text.strip()

@st.cache_data(ttl=3600)
def add_topics(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    questions = tuple(df["question"].tolist())
    k = min(N_CLUSTERS, len(df))

    with st.spinner("Clustering questions into topics…"):
        vecs = _embed(questions)

    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    vecs_n = vecs / np.where(norms == 0, 1, norms)

    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    df = df.copy()
    df["cluster_id"] = km.fit_predict(vecs_n)

    cluster_labels: dict[int, str] = {}
    for cid in range(k):
        sample = tuple(df[df["cluster_id"] == cid]["question"].tolist()[:8])
        cluster_labels[cid] = _label(sample)

    df["topic"] = df["cluster_id"].map(cluster_labels)
    return df

# ──────────────────────────── UI ────────────────────────────────
st.title("🛡️ SmartCAT Admin — Question Analytics")
st.caption("See which users ask which types of questions and how often.")

if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()

df_raw = load_qa_log()

if df_raw.empty:
    st.warning("No questions in qa_log yet.")
    st.stop()

df = add_topics(df_raw)

# ── Filters ──────────────────────────────────────────────────────
st.divider()
fc1, fc2, fc3 = st.columns(3)
with fc1:
    users = ["All Users"] + sorted(df["user_id"].dropna().unique().tolist())
    sel_user = st.selectbox("👤 Filter by User", users)
with fc2:
    topics = ["All Topics"] + sorted(df["topic"].unique().tolist())
    sel_topic = st.selectbox("🏷️ Filter by Topic", topics)
with fc3:
    dates = sorted(df["date"].unique())
    if len(dates) >= 2:
        date_range = st.date_input("📅 Date Range", value=(dates[0], dates[-1]))
    else:
        date_range = (dates[0], dates[0]) if dates else (None, None)

dff = df.copy()
if sel_user  != "All Users":  dff = dff[dff["user_id"] == sel_user]
if sel_topic != "All Topics": dff = dff[dff["topic"]   == sel_topic]
if date_range and date_range[0]:
    dff = dff[(dff["date"] >= date_range[0]) & (dff["date"] <= date_range[-1])]

# ── KPI Cards ────────────────────────────────────────────────────
st.divider()
k1, k2, k3, k4 = st.columns(4)
k1.metric("📨 Total Questions",  len(dff))
k2.metric("👥 Unique Users",     dff["user_id"].nunique())
k3.metric("🏷️ Topics Found",     dff["topic"].nunique())
top_user = dff["user_id"].value_counts().idxmax() if not dff.empty else "—"
k4.metric("🏆 Most Active User", top_user)

st.divider()

# ── Chart row 1 ──────────────────────────────────────────────────
c1, c2 = st.columns(2)

with c1:
    st.subheader("📊 Questions by Topic")
    tc = (
        dff.groupby("topic").size().reset_index(name="count")
        .sort_values("count", ascending=False)
    )
    fig = px.bar(tc, x="topic", y="count", color="topic",
                 color_discrete_sequence=px.colors.qualitative.Set2,
                 labels={"topic": "Topic", "count": "Questions"})
    fig.update_layout(showlegend=False, xaxis_tickangle=-30, margin=dict(t=10))
    st.plotly_chart(fig, use_container_width=True)

with c2:
    st.subheader("👤 Questions per User")
    uc = (
        dff.groupby("user_id").size().reset_index(name="count")
        .sort_values("count", ascending=False).head(10)
    )
    fig2 = px.bar(uc, x="user_id", y="count", color="user_id",
                  color_discrete_sequence=px.colors.qualitative.Pastel,
                  labels={"user_id": "User", "count": "Questions"})
    fig2.update_layout(showlegend=False, xaxis_tickangle=-30, margin=dict(t=10))
    st.plotly_chart(fig2, use_container_width=True)

# ── Heatmap ───────────────────────────────────────────────────────
st.subheader("🔥 User × Topic Heatmap — Kaun kya zyada pooch raha hai")
heat = dff.groupby(["user_id", "topic"]).size().reset_index(name="count")
if not heat.empty:
    pivot = heat.pivot(index="user_id", columns="topic", values="count").fillna(0)
    fig3 = px.imshow(
        pivot, aspect="auto", color_continuous_scale="Blues",
        labels=dict(x="Topic", y="User", color="Questions"),
        text_auto=True,
    )
    fig3.update_layout(height=max(300, len(pivot) * 45), margin=dict(t=10))
    st.plotly_chart(fig3, use_container_width=True)

# ── Timeline ──────────────────────────────────────────────────────
st.subheader("📅 Questions Over Time (by Topic)")
tl = dff.groupby(["date", "topic"]).size().reset_index(name="count")
if not tl.empty:
    fig4 = px.line(tl, x="date", y="count", color="topic", markers=True,
                   labels={"date": "Date", "count": "Questions", "topic": "Topic"},
                   color_discrete_sequence=px.colors.qualitative.Set1)
    fig4.update_layout(margin=dict(t=10))
    st.plotly_chart(fig4, use_container_width=True)

# ── Per-user topic breakdown ──────────────────────────────────────
st.subheader("🔍 Per-User Topic Breakdown")
user_topic = (
    dff.groupby(["user_id", "topic"]).size().reset_index(name="count")
    .sort_values(["user_id", "count"], ascending=[True, False])
)
if not user_topic.empty:
    fig5 = px.bar(user_topic, x="user_id", y="count", color="topic", barmode="stack",
                  labels={"user_id": "User", "count": "Questions", "topic": "Topic"},
                  color_discrete_sequence=px.colors.qualitative.Vivid)
    fig5.update_layout(xaxis_tickangle=-30, margin=dict(t=10))
    st.plotly_chart(fig5, use_container_width=True)

# ── Raw log ───────────────────────────────────────────────────────
st.divider()
st.subheader("📋 Full Question Log")
st.dataframe(
    dff[["ts", "user_id", "topic", "question"]]
    .sort_values("ts", ascending=False)
    .reset_index(drop=True),
    use_container_width=True,
    height=320,
)

# ── Logout ────────────────────────────────────────────────────────
st.divider()
if st.button("🚪 Logout"):
    st.session_state.admin_ok = False
    st.rerun()
