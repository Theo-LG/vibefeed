"""Mistral AI news scraper — uses Jina reader (SPA, no RSS)."""
import re
import httpx
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from .jina import _parse_date

JINA_URL = "https://r.jina.ai/https://mistral.ai/news"
HEADERS_JINA = {"Accept": "text/plain", "User-Agent": "Mozilla/5.0"}
HEADERS_HTML = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"}

_NEWS_LINK = re.compile(r'\[.*?\]\((https://mistral\.ai/news/[a-z0-9-]+/?)\)', re.DOTALL)
_DATE_SUFFIX = re.compile(r'\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}.*')


def _fetch_title(url: str) -> str:
    try:
        r = httpx.get(url, timeout=10, follow_redirects=True, headers=HEADERS_HTML)
        soup = BeautifulSoup(r.text, "html.parser")
        title = soup.find("title")
        if title:
            return title.get_text(strip=True).split(" | ")[0].strip()
    except Exception:
        pass
    return ""


def fetch(blog_url: str, _extract_fn: Callable) -> list[dict]:
    try:
        r = httpx.get(JINA_URL, timeout=30, headers=HEADERS_JINA)
        r.raise_for_status()
        text = r.text
    except Exception as e:
        print(f"  [FETCH ERROR] mistral.ai/news: {e}")
        return []

    seen: set[str] = set()
    candidates: list[dict] = []

    for m in _NEWS_LINK.finditer(text):
        url = m.group(1).rstrip("/")
        if url in seen:
            continue
        seen.add(url)
        published_date = _parse_date(m.group(0))
        candidates.append({"url": url, "date": published_date})

    # Fetch titles in parallel
    with ThreadPoolExecutor(max_workers=len(candidates)) as pool:
        titles = list(pool.map(_fetch_title, [c["url"] for c in candidates]))

    articles = [
        {**c, "title": t}
        for c, t in zip(candidates, titles)
        if t
    ]

    print(f"  [Mistral] {len(articles)} article(s) found.")
    return articles[:30]
