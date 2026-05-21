"""Phil Schmid blog scraper — BS4 for listing, per-article fetch for accurate dates."""
import httpx
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin
from typing import Callable

from .jina import HEADERS, _ARTICLE_PATH, _SKIP_PATH, _parse_date

BLOG_URL = "https://www.philschmid.de/"


def _fetch_date_and_title(url: str) -> tuple[str, str]:
    try:
        r = httpx.get(url, timeout=10, follow_redirects=True, headers=HEADERS)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        title_tag = soup.find("h1")
        title = title_tag.get_text(strip=True) if title_tag else ""
        date = _parse_date(soup.get_text(separator=" ")[:500])
        return title, date
    except Exception:
        return "", ""


def fetch(blog_url: str, _extract_fn: Callable) -> list[dict]:
    try:
        r = httpx.get(blog_url, timeout=30, follow_redirects=True, headers=HEADERS)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print(f"  [FETCH ERROR] {blog_url}: {e}")
        return []

    seen: set[str] = set()
    urls: list[str] = []

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].split("?")[0].rstrip("/")
        url = href if href.startswith("http") else urljoin(blog_url, href)
        if blog_url.split("//")[1].split("/")[0] not in url:
            continue
        if not _ARTICLE_PATH.search(href):
            continue
        if _SKIP_PATH.search(href):
            continue
        if url in seen:
            continue
        seen.add(url)
        urls.append(url)

    with ThreadPoolExecutor(max_workers=min(len(urls), 10)) as pool:
        results = list(pool.map(_fetch_date_and_title, urls))

    _SKIP_TITLES = {"Newsletter", "Philipp Schmid"}

    articles = [
        {"url": url, "title": title, "date": date}
        for url, (title, date) in zip(urls, results)
        if len(title) >= 10 and title not in _SKIP_TITLES
    ]

    print(f"  [PhilSchmid] {len(articles)} article(s) found.")
    return articles[:30]
