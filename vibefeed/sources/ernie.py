"""ERNIE (Baidu) blog scraper — Jina listing, no RSS available."""
import re
import httpx
from datetime import date

JINA_URL = "https://r.jina.ai/https://ernie.baidu.com/blog"
HEADERS = {"Accept": "text/plain", "User-Agent": "AIFeed-personal/1.0 (personal AI news aggregator; not for redistribution)"}

_ENTRY = re.compile(
    r'\[!\[Image \d+\]\([^)]+/cover\.[a-z]+\)\]'
    r'\((https://ernie\.baidu\.com/blog/posts/([^/]+)/)\)'
    r'\n\n(.+?)\n\n'
    r'\[\]\(',
    re.DOTALL,
)


def _date_from_slug(slug: str) -> str:
    # Many slugs embed MMDD like ernie-5.1-0508-release or ernie-5.0-preview-1220-...
    m = re.search(r'-(\d{2})(\d{2})(?:-|$)', slug)
    if m:
        mm, dd = int(m.group(1)), int(m.group(2))
        if 1 <= mm <= 12 and 1 <= dd <= 31:
            today = date.today()
            year = today.year if mm <= today.month else today.year - 1
            try:
                return date(year, mm, dd).isoformat()
            except ValueError:
                pass
    return "2000-01-01"  # no date in slug → exclude from 30-day window


def fetch(blog_url: str, _) -> list[dict]:
    try:
        r = httpx.get(JINA_URL, timeout=30, headers=HEADERS)
        r.raise_for_status()
        text = r.text
    except Exception as e:
        print(f"  [FETCH ERROR] ernie.baidu.com: {e}")
        return []

    seen: set[str] = set()
    articles: list[dict] = []

    for m in _ENTRY.finditer(text):
        url, slug, desc = m.group(1), m.group(2), m.group(3).strip()
        if url in seen:
            continue
        seen.add(url)
        title = re.split(r'\.\s', desc)[0].strip()[:120] or slug
        articles.append({
            "title":   title,
            "url":     url,
            "date":    _date_from_slug(slug),
            "summary": desc,
        })

    print(f"  [ERNIE] {len(articles)} article(s) found.")
    return articles[:30]
