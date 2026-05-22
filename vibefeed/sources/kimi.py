"""Kimi (Moonshot AI) blog scraper — Jina listing."""
import re
import httpx
from datetime import datetime

JINA_URL = "https://r.jina.ai/https://www.kimi.com/blog/"
HEADERS = {"Accept": "text/plain", "User-Agent": "AIFeed-personal/1.0 (personal AI news aggregator; not for redistribution)"}

# [![Image N: Title](cover)] #### Title YYYY/MM/DD](url)
_ENTRY = re.compile(
    r'\[!\[Image \d+: [^\]]*\]\([^)]+\) ####\s+(.+?)\s+(\d{4}/\d{2}/\d{2})\]'
    r'\((https://[^)]+)\)'
)


def _parse_date(raw: str) -> str:
    try:
        return datetime.strptime(raw, "%Y/%m/%d").date().isoformat()
    except ValueError:
        return raw


def fetch(blog_url: str, _) -> list[dict]:
    try:
        r = httpx.get(JINA_URL, timeout=30, headers=HEADERS)
        r.raise_for_status()
        text = r.text
    except Exception as e:
        print(f"  [FETCH ERROR] kimi.com/blog: {e}")
        return []

    seen: set[str] = set()
    articles: list[dict] = []

    for m in _ENTRY.finditer(text):
        title, date_raw, url = m.group(1).strip(), m.group(2), m.group(3).strip()
        if url in seen:
            continue
        seen.add(url)
        articles.append({"title": title, "url": url, "date": _parse_date(date_raw)})

    print(f"  [Kimi] {len(articles)} article(s) found.")
    return articles[:30]
