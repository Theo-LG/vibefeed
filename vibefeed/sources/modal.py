"""Modal blog scraper — uses Jina reader (JS-rendered, no RSS)."""
import re
import httpx
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from .jina import _parse_date

JINA_URL = "https://r.jina.ai/https://modal.com/blog"
HEADERS_JINA = {"Accept": "text/plain", "User-Agent": "Mozilla/5.0"}
HEADERS_HTML = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"}

_BLOG_LINK = re.compile(
    r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w* \d{1,2}, \d{4})\s+'
    r'[#]{2,4}\s+[^\]]+\]\s*\((https://modal\.com/blog/[a-z0-9-]+)\)',
)


def _fetch_title(url: str) -> str:
    try:
        r = httpx.get(url, timeout=10, follow_redirects=True, headers=HEADERS_HTML)
        soup = BeautifulSoup(r.text, "html.parser")
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)
    except Exception:
        pass
    return ""


def fetch(blog_url: str, _extract_fn: Callable) -> list[dict]:
    try:
        r = httpx.get(JINA_URL, timeout=30, headers=HEADERS_JINA)
        r.raise_for_status()
        text = r.text
    except Exception as e:
        print(f"  [FETCH ERROR] modal.com/blog: {e}")
        return []

    seen: set[str] = set()
    candidates: list[dict] = []

    for m in _BLOG_LINK.finditer(text):
        url = m.group(2)
        if url in seen:
            continue
        seen.add(url)
        candidates.append({"url": url, "date": _parse_date(m.group(1))})

    with ThreadPoolExecutor(max_workers=min(len(candidates), 10)) as pool:
        titles = list(pool.map(_fetch_title, [c["url"] for c in candidates]))

    articles = [
        {**c, "title": t}
        for c, t in zip(candidates, titles)
        if t
    ]

    print(f"  [Modal] {len(articles)} article(s) found.")
    return articles[:30]
