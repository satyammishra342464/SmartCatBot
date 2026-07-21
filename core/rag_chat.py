"""Build the grounded prompt and stream answers from Gemini."""
from __future__ import annotations

SYSTEM_INSTRUCTIONS = """You are a document Q&A assistant.
Answer the user's question using ONLY the context excerpts provided below.

Rules:
- If the answer is not present in the context, say clearly that you could not find it in the uploaded documents. Never guess or use outside knowledge.
- Answer in the same language the user asked in (English, Hindi, or Hinglish).
- Be concise and specific. Quote figures, dates, and names exactly as they appear in the context.
- When helpful, mention which document (and page) the information came from, e.g. (Slip A1.pdf, page 2)."""


def build_prompt(question: str, context_chunks: list[dict], history: list[dict]) -> str:
    context_lines = []
    for i, chunk in enumerate(context_chunks, start=1):
        location = chunk["doc"] + (f", page {chunk['page']}" if chunk.get("page") else "")
        context_lines.append(f"[{i}] ({location})\n{chunk['text']}")
    context = "\n\n".join(context_lines) if context_lines else "(no context retrieved)"

    conversation = ""
    if history:
        turns = [f"{m['role'].upper()}: {m['content']}" for m in history[-6:]]
        conversation = "Conversation so far (for follow-up context only):\n" + "\n".join(turns) + "\n\n"

    return (
        f"{SYSTEM_INSTRUCTIONS}\n\n"
        f"{conversation}"
        f"Context excerpts from the uploaded documents:\n{context}\n\n"
        f"Question: {question}\n\n"
        f"Answer:"
    )


def stream_answer(client, model: str, prompt: str):
    """Yield answer text chunks as they arrive from Gemini."""
    for chunk in client.models.generate_content_stream(model=model, contents=prompt):
        if chunk.text:
            yield chunk.text
