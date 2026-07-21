"""Parse crawled UNICEDE HTML pages into RAG-ready structured records.

Each page becomes: {url, title, section, version, text, tables}.
Tables are kept twice on purpose — inline as markdown inside `text` (for the
vector index) and as structured header/row lists in `tables` (for SQLite
exact-lookup loading later).
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

VERSION_RE = re.compile(r"[_-](2-\d+)$")
BOILERPLATE_LINES = {"jump to main content", "search", "home", "print"}


def parse_page(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    title = soup.title.get_text(strip=True) if soup.title else url

    for tag in soup(["script", "style", "noscript", "nav", "header", "footer"]):
        tag.decompose()

    body = soup.body or soup

    tables = []
    for table in body.find_all("table"):
        headers, rows = _extract_table(table)
        if rows:
            tables.append({"headers": headers, "rows": rows})
            table.replace_with(soup.new_string("\n" + _to_markdown(headers, rows) + "\n"))
        else:
            table.decompose()

    text = body.get_text("\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = "\n".join(
        line for line in text.split("\n") if line.strip().lower() not in BOILERPLATE_LINES
    )
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    path = urlparse(url).path
    parts = path.strip("/").split("/")
    section = parts[0] if len(parts) > 1 else "root"
    stem = parts[-1].rsplit(".", 1)[0] if parts else ""
    match = VERSION_RE.search(stem)
    version = match.group(1).replace("-", ".") if match else None

    return {
        "url": url,
        "title": title,
        "section": section,
        "version": version,
        "text": text,
        "tables": tables,
    }


def _extract_table(table) -> tuple[list[str], list[list[str]]]:
    all_rows: list[list[str]] = []
    for tr in table.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
        if any(cells):
            all_rows.append(cells)
    if not all_rows:
        return [], []
    first_tr = table.find("tr")
    has_header = first_tr is not None and first_tr.find("th") is not None
    if has_header:
        return all_rows[0], all_rows[1:]
    return [], all_rows


def _to_markdown(headers: list[str], rows: list[list[str]]) -> str:
    lines = []
    if headers:
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("|" + " --- |" * len(headers))
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)
