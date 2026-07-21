"""Live web search tool — a separate Gemini call with Google Search grounding.

Kept as its own model call because the Gemini API does not allow mixing the
google_search tool with custom function declarations in one request.
"""
from __future__ import annotations


def make_web_search(client, model: str):
    def web_search(query: str) -> dict:
        try:
            from google.genai import types

            response = client.models.generate_content(
                model=model,
                contents=(
                    "Use Google Search and answer factually and concisely (5-10 sentences max), "
                    "focusing on insurance/catastrophe-modelling context if relevant: " + query
                ),
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                ),
            )
            sources = []
            candidate = response.candidates[0] if response.candidates else None
            metadata = getattr(candidate, "grounding_metadata", None)
            chunks = getattr(metadata, "grounding_chunks", None) or []
            for chunk in chunks:
                web = getattr(chunk, "web", None)
                if web and web.uri:
                    sources.append({"title": web.title or web.uri, "url": web.uri})
            return {"summary": response.text or "(no result)", "sources": sources[:6]}
        except Exception as exc:
            return {"error": f"web search unavailable: {exc}"}

    return web_search
