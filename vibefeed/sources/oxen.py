"""Oxen AI blog scraper — Jina reader, dates in M/D/YYYY format."""
import re
import httpx
from typing import Callable
from datetime import datetime

JINA_URL = "https://r.jina.ai/https://www.oxen.ai/blog"
HEADERS = {"Accept": "text/plain", "User-Agent": "AIFeed-personal/1.0 (personal AI news aggregator; not for redistribution)"}

# Each card: [![Image N: Title](cover) content [![Image N+1: Author](avatar) Author DATE min read](url)
_ARTICLE = re.compile(
    r'\[!\[Image \d+: ([^\]]{5,}?)\]\(https://storage\.ghost\.io[^)]+\)'
    r'.+?(\d{1,2}/\d{1,2}/\d{4}).+?min read\]'
    r'\((https://www\.oxen\.ai/blog/[a-z0-9][a-z0-9-]+)\)',
    re.DOTALL
)


def _parse_date(raw: str) -> str:
    parts = raw.split("/")
    try:
        return datetime(int(parts[2]), int(parts[0]), int(parts[1])).date().isoformat()
    except (ValueError, IndexError):
        from datetime import date
        return date.today().isoformat()


def fetch(blog_url: str, _extract_fn: Callable) -> list[dict]:
    try:
        r = httpx.get(JINA_URL, timeout=30, headers=HEADERS)
        r.raise_for_status()
        text = r.text
    except Exception as e:
        print(f"  [FETCH ERROR] oxen.ai/blog: {e}")
        return []

    seen: set[str] = set()
    articles: list[dict] = []

    for m in _ARTICLE.finditer(text):
        title, date_raw, url = m.group(1).strip(), m.group(2), m.group(3)
        if url in seen:
            continue
        seen.add(url)
        articles.append({"title": title, "url": url, "date": _parse_date(date_raw)})

    print(f"  [Oxen] {len(articles)} article(s) found.")
    return articles[:30]
