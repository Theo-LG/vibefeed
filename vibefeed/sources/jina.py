"""Direct HTTP + BS4 heuristic fetcher — no LLM needed for article listing."""
import re
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import date
from typing import Callable

HEADERS = {"User-Agent": "AIFeed-personal/1.0 (personal AI news aggregator; not for redistribution)"}

# Patterns that suggest a URL is an article (not a nav/tag/category link)
_ARTICLE_PATH = re.compile(r"/[a-z0-9-]{10,}/?$")
_SKIP_PATH = re.compile(r"/(tag|tags|category|categories|topics|topic|author|authors|page|search|product|products)/", re.IGNORECASE)
_SKIP_DOMAIN = re.compile(r"^https?://(legal|privacy|terms|careers|jobs)\.", re.IGNORECASE)
_DATE_PATTERN = re.compile(
    r"(?<!\w)(\d{4}[-/]\d{2}[-/]\d{2}|"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4})(?!\w)",
    re.IGNORECASE,
)


def _parse_date(text: str) -> str:
    from email.utils import parsedate_to_datetime
    import datetime
    m = _DATE_PATTERN.search(text)
    if not m:
        return date.today().isoformat()
    raw = m.group(0)
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%B %d, %Y", "%B %d %Y", "%b %d, %Y", "%b %d %Y"):
        try:
            return datetime.datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            pass
    return date.today().isoformat()


def fetch(blog_url: str, extract_fn: Callable) -> list[dict]:
    # extract_fn is ignored — BS4 heuristic replaces LLM for listing
    try:
        r = httpx.get(blog_url, timeout=30, follow_redirects=True, headers=HEADERS)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print(f"  [FETCH ERROR] {blog_url}: {e}")
        return []

    # Page-level date fallback from <meta property="article:published_time">
    _meta_date: str | None = None
    meta = soup.find("meta", property="article:published_time") or soup.find("meta", attrs={"name": "date"})
    if meta and meta.get("content"):
        _meta_date = _parse_date(meta["content"])

    seen: set[str] = set()
    articles: list[dict] = []

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].split("?")[0].rstrip("/")
        url = href if href.startswith("http") else urljoin(blog_url, href)

        # skip external links, anchors, and non-article paths
        if blog_url.split("//")[1].split("/")[0] not in url:
            continue
        if not _ARTICLE_PATH.search(href):
            continue
        if _SKIP_PATH.search(href):
            continue
        if _SKIP_DOMAIN.match(url):
            continue
        if url in seen:
            continue
        seen.add(url)

        heading = a_tag.find(["h1", "h2", "h3", "h4"])
        title = heading.get_text(strip=True) if heading else a_tag.get_text(strip=True).splitlines()[0].strip()
        if len(title) < 10:
            continue

        # look for a date: <time datetime="...">, card text, page meta, then today
        card = a_tag.find_parent(["article", "li", "div", "section"]) or a_tag
        time_tag = card.find("time", attrs={"datetime": True})
        if time_tag:
            published_date = _parse_date(time_tag["datetime"])
        else:
            card_date = _parse_date(card.get_text(separator=" "))
            published_date = card_date if card_date != date.today().isoformat() else (_meta_date or card_date)

        articles.append({"title": title, "url": url, "date": published_date})

    print(f"  [BS4] {len(articles)} article(s) found.")
    return articles[:30]
