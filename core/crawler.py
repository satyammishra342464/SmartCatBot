"""Polite UNICEDE site crawler: sitemap seed + BFS link-following, resumable.

Pages already on disk are re-used (no re-fetch), so an interrupted crawl can
simply be re-run and it continues where it left off.
"""
from __future__ import annotations

import json
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

import requests

BASE_URL = "https://unicede.air-worldwide.com/"
HOST = "unicede.air-worldwide.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; DocChatbot-Crawler/0.1; internal research POC)"}
SKIP_EXTENSIONS = (
    ".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".pdf", ".zip", ".xml", ".woff", ".woff2", ".ttf", ".eot",
)

HREF_RE = re.compile(r'href=["\']([^"\'#]+)', re.IGNORECASE)
MANIFEST_FILE = "_manifest.json"


def url_to_filename(url: str) -> str:
    path = urlparse(url).path.lstrip("/") or "index.html"
    return path.replace("/", "__")


def sitemap_urls(session: requests.Session) -> list[str]:
    try:
        resp = session.get(urljoin(BASE_URL, "sitemap.xml"), timeout=30)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except (requests.RequestException, ET.ParseError):
        return []
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    return [loc.text.strip() for loc in root.findall(".//sm:loc", ns) if loc.text]


def _normalize(base: str, href: str) -> str | None:
    href = href.strip()
    if not href or href.startswith(("mailto:", "javascript:", "tel:")):
        return None
    absolute = urldefrag(urljoin(base, href)).url
    parsed = urlparse(absolute)
    if parsed.scheme not in ("http", "https") or parsed.netloc != HOST:
        return None
    if parsed.path.lower().endswith(SKIP_EXTENSIONS):
        return None
    return f"https://{HOST}{parsed.path}"


def crawl(raw_dir: Path, delay: float = 0.4, max_pages: int | None = None, log=print) -> dict:
    raw_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update(HEADERS)

    manifest_path = raw_dir / MANIFEST_FILE
    manifest: dict[str, str] = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    queue: list[str] = []
    seen: set[str] = set()

    def enqueue(candidate: str | None) -> None:
        if candidate and candidate not in seen:
            seen.add(candidate)
            queue.append(candidate)

    enqueue(urljoin(BASE_URL, "index.html"))
    for loc in sitemap_urls(session):
        enqueue(_normalize(BASE_URL, loc))
    log(f"Seeded {len(queue)} URLs (sitemap + home)")

    stats = {"fetched": 0, "cached": 0, "failed": 0}

    try:
        while queue:
            if max_pages is not None and (stats["fetched"] + stats["cached"]) >= max_pages:
                break
            url = queue.pop(0)
            target = raw_dir / url_to_filename(url)

            html: str | None = None
            if target.exists():
                html = target.read_text(encoding="utf-8", errors="ignore")
                stats["cached"] += 1
            else:
                try:
                    resp = session.get(url, timeout=30)
                except requests.RequestException as exc:
                    log(f"FAILED {url}: {exc}")
                    stats["failed"] += 1
                    time.sleep(delay)
                    continue
                time.sleep(delay)
                content_type = resp.headers.get("Content-Type", "text/html")
                if resp.status_code != 200 or "html" not in content_type:
                    stats["failed"] += 1
                    continue
                html = resp.text
                target.write_text(html, encoding="utf-8")
                stats["fetched"] += 1

            manifest[url] = target.name
            for href in HREF_RE.findall(html):
                enqueue(_normalize(url, href))

            done = stats["fetched"] + stats["cached"]
            if done % 50 == 0:
                log(f"[{done}] fetched={stats['fetched']} cached={stats['cached']} "
                    f"failed={stats['failed']} queue={len(queue)}")
    finally:
        manifest_path.write_text(json.dumps(manifest, indent=1), encoding="utf-8")

    log(f"Crawl finished: {stats}")
    return stats
