"""SmartCAT agentic loop: Gemini function calling over a dynamic tool registry.

Tools are passed in as {name: callable(str) -> payload}; declarations are built
only for the tools actually available this session. The model decides which to
call, can retry with rephrased queries, and always produces a final answer
(a forced tools-off call fires if the tool budget runs out).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from google.genai import types

SYSTEM_PROMPT = """You are SmartCAT, an expert CAT (catastrophe) modelling assistant for insurance/reinsurance analysts.

Your knowledge base contains the official UNICEDE (Verisk/AIR) reference corpus PLUS internal CAT
modelling training documents (e.g. RMS RiskLink slip coding rules for limits, deductibles,
sublimits, and Account/Location file fields).

Tool priority order:
1. search_knowledge / lookup_codes — the curated knowledge base. ALWAYS try these first for any domain question.
2. search_uploaded_docs — documents the user uploaded in THIS chat session. Use when the question refers to "this document/slip" or uploaded content.
3. web_search — live Google search. Use ONLY when the knowledge base clearly lacks the answer and the question is factual (industry news, vendor updates, definitions). Prefix web-sourced statements with "🌐".
4. calculate — exact arithmetic (limits, deductibles, layer losses, percentages). Use this for ANY numeric computation instead of computing yourself.
5. lookup_location — postal/pincode and place lookups from the GeoNames database.

Answer policy — follow strictly:
1. Grounded first: answer from tool results and cite source page titles with URLs.
2. CODE VERIFICATION: never state a numeric code (occupancy, construction, CRESTA, peril, country, FIPS) unless it appeared verbatim in a tool result in this conversation. If you know a code from memory, verify it via lookup_codes BEFORE stating it. If verification fails, say the code was not found — NEVER invent or guess codes.
3. If neither the knowledge base nor the web has the answer: answer from general CAT modelling knowledge, but begin that part with "⚠️ Not found in the knowledge base — answering from general CAT modelling knowledge:" (translate the label to the user's language if they are not writing in English).
4. ALWAYS reply in English by default. Switch to Hindi or Hinglish ONLY if the user's own message is written in that language. Be concise and specific; quote codes and values exactly.
5. Tool budget: at most 6 tool calls per question; never repeat a query you already tried. If 2-3 knowledge-base searches miss, escalate to web_search once, then answer.
"""

MAX_TURNS = 8

# name -> (description, parameter name, parameter description)
TOOL_SPECS: dict[str, tuple[str, str, str]] = {
    "search_knowledge": (
        "Semantic + keyword search over UNICEDE/AIR reference pages and internal training docs "
        "(RMS RiskLink slip coding rules, limits/deductibles fields). Use for concepts, "
        "definitions, perils, file formats, validation rules, RMS field guidance.",
        "query", "Search query in English",
    ),
    "lookup_codes": (
        "Exact keyword search over code tables parsed from UNICEDE: CRESTA/area codes, peril "
        "codes, country codes, occupancy/construction class codes, valid field values. Use for "
        "any specific code or list of valid values, and to VERIFY codes before stating them.",
        "query", "Keywords, e.g. 'Australia country code' or 'occupancy 316'",
    ),
    "web_search": (
        "Live Google web search. Use only when the knowledge base does not contain the answer "
        "(industry news, vendor product updates, general definitions).",
        "query", "Web search query in English",
    ),
    "calculate": (
        "Safe arithmetic calculator. Supports + - * / // % ** parentheses and min/max/abs/round/"
        "sqrt. Use for ALL numeric computations (layer losses, deductible math, percentages).",
        "expression", "Arithmetic expression, e.g. 'min(40e6, 100e6) - 25e6'",
    ),
    "lookup_location": (
        "Postal/pincode and place lookup from the GeoNames worldwide postal database. "
        "Use for questions like 'pincode of <place>' or 'which place is postal code X'.",
        "query", "Place name or postal code, optionally with country",
    ),
    "search_uploaded_docs": (
        "Semantic search over documents the user uploaded in this chat session. Use when the "
        "question is about the uploaded document/slip content.",
        "query", "Search query about the uploaded document",
    ),
}


@dataclass
class AgentResult:
    answer: str
    tool_calls: list[dict] = field(default_factory=list)
    sources: list[dict] = field(default_factory=list)


def _declarations(tool_names) -> types.Tool:
    declarations = []
    for name in tool_names:
        description, param, param_desc = TOOL_SPECS[name]
        declarations.append(
            types.FunctionDeclaration(
                name=name,
                description=description,
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={param: types.Schema(type=types.Type.STRING, description=param_desc)},
                    required=[param],
                ),
            )
        )
    return types.Tool(function_declarations=declarations)


def _collect_sources(payload, result: AgentResult) -> None:
    items = []
    if isinstance(payload, list):
        items = payload[:4]
    elif isinstance(payload, dict):
        items = payload.get("sources", [])[:4]
    for item in items:
        if isinstance(item, dict) and item.get("url"):
            result.sources.append({"title": item.get("title") or item["url"], "url": item["url"]})


def run_agent(question: str, history: list[dict], client, model: str,
              tools: dict[str, Callable[[str], object]]) -> AgentResult:
    available = [name for name in TOOL_SPECS if name in tools]
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=[_declarations(available)],
        temperature=0.2,
    )

    contents: list[types.Content] = []
    for message in history[-8:]:
        role = "user" if message["role"] == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=message["content"])]))
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=question)]))

    result = AgentResult(answer="")
    seen_queries: set[tuple[str, str]] = set()
    for _ in range(MAX_TURNS):
        response = client.models.generate_content(model=model, contents=contents, config=config)
        calls = response.function_calls or []
        if not calls:
            result.answer = response.text or "(empty response)"
            return result

        contents.append(response.candidates[0].content)
        response_parts = []
        for call in calls:
            args = dict(call.args or {})
            arg_value = str(next(iter(args.values()), ""))
            query_key = (call.name, arg_value.strip().lower())
            if query_key in seen_queries:
                payload = {
                    "note": "Duplicate query — you already have these results above. "
                            "STOP searching and write your final answer now."
                }
            elif call.name in tools:
                payload = tools[call.name](arg_value)
                _collect_sources(payload, result)
            else:
                payload = {"error": f"unknown tool: {call.name}"}
            seen_queries.add(query_key)
            result.tool_calls.append({
                "tool": call.name,
                "query": arg_value,
                "hits": len(payload) if isinstance(payload, list) else 1,
            })
            response_parts.append(
                types.Part.from_function_response(name=call.name, response={"result": payload})
            )
        contents.append(types.Content(role="tool", parts=response_parts))

    # Tool budget exhausted — force a final answer with tools disabled so the
    # user always gets an answer instead of a limit error.
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=(
        "You have used your entire tool budget. Do NOT call any more tools. Write your final "
        "answer NOW: use whatever the tool results above contain, and fill any gaps from general "
        "CAT modelling knowledge with the required warning label."
    ))]))
    final_config = types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT, temperature=0.2)
    response = client.models.generate_content(model=model, contents=contents, config=final_config)
    result.answer = response.text or "(no answer produced)"
    return result
