"""Qwen research scraper — Jina listing on /research, articles via ?id= pattern."""
import re
import httpx
from typing import Callable

JINA_URL = "https://r.jina.ai/https://qwen.ai/research"
HEADERS = {"Accept": "text/plain", "User-Agent": "AIFeed-personal/1.0 (personal AI news aggregator; not for redistribution)"}

# Matches blocks: "Release\n\n2026/05/20\n\nQwen3.7: The Agent Frontier\n"
_ROW = re.compile(r'(?:Release|Open-Source)\n\n(\d{4}/\d{2}/\d{2})\n\n([^\n]{5,})\n')


def _title_to_id(title: str) -> str:
    # "Qwen3.7: The Agent Frontier" → "qwen3.7"
    return title.split(":")[0].strip().lower()


def fetch(blog_url: str, _extract_fn: Callable) -> list[dict]:
    try:
        r = httpx.get(JINA_URL, timeout=30, headers=HEADERS)
        r.raise_for_status()
        text = r.text
    except Exception as e:
        print(f"  [FETCH ERROR] qwen.ai/research: {e}")
        return []

    seen: set[str] = set()
    articles: list[dict] = []

    for m in _ROW.finditer(text):
        date = m.group(1).replace("/", "-")
        title = m.group(2).strip()
        if not title or title.lower() in ("titre", "title"):
            continue
        url = f"https://qwen.ai/blog?id={_title_to_id(title)}"
        if url in seen:
            continue
        seen.add(url)
        articles.append({"title": title, "url": url, "date": date})

    print(f"  [Qwen] {len(articles)} article(s) found.")
    return articles[:30]
