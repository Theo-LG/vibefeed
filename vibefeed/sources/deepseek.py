"""deepseek.ai fan-site blog scraper — Jina listing + sitemap URL matching."""
import re
import httpx
from datetime import date
from xml.etree import ElementTree as ET

JINA_URL    = "https://r.jina.ai/https://deepseek.ai/blog"
SITEMAP_URL = "https://deepseek.ai/sitemap.xml"
HEADERS = {"Accept": "text/plain", "User-Agent": "AIFeed-personal/1.0 (personal AI news aggregator; not for redistribution)"}

_MONTHS = {
    "january":1,"february":2,"march":3,"april":4,"may":5,"june":6,
    "july":7,"august":8,"september":9,"october":10,"november":11,"december":12,
}

_ENTRY = re.compile(
    r'((?:January|February|March|April|May|June|July|August|September|'
    r'October|November|December)\s+\d{1,2},\s+\d{4})'
    r'[^\n]*\n+###\s+([^\n]{5,})\n+([^\n#]{10,})',
    re.IGNORECASE,
)

_STOPWORDS = {"the","a","an","of","and","in","to","s","is","are","for","on","at","by","its","how"}


def _parse_date(raw: str) -> str:
    parts = re.split(r'[\s,]+', raw.strip().lower())
    try:
        return date(int(parts[2]), _MONTHS[parts[0]], int(parts[1])).isoformat()
    except Exception:
        return date.today().isoformat()


def _to_slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _find_url(title: str, sitemap_slugs: list[str]) -> str:
    base = _to_slug(title.split(":")[0].strip())
    base_tokens = set(base.split("-")) - _STOPWORDS

    # exact match
    if base in sitemap_slugs:
        return f"https://deepseek.ai/blog/{base}"

    # prefix match — only if base is specific enough (≥ 2 meaningful tokens)
    if len(base_tokens) >= 2:
        for slug in sitemap_slugs:
            if slug.startswith(base):
                return f"https://deepseek.ai/blog/{slug}"

    # token-overlap (threshold ≥ 3 to avoid false positives on generic titles)
    if len(base_tokens) >= 2:
        best_score, best = 0, None
        for slug in sitemap_slugs:
            score = len(base_tokens & set(slug.split("-")))
            if score > best_score:
                best_score, best = score, slug
        if best_score >= 3:
            return f"https://deepseek.ai/blog/{best}"

    # fallback: generate from full title slug
    return f"https://deepseek.ai/blog/{_to_slug(title)[:80]}"


def fetch(blog_url: str, _) -> list[dict]:
    # Sitemap → known slugs
    sitemap_slugs: list[str] = []
    try:
        r = httpx.get(SITEMAP_URL, timeout=20, headers={"User-Agent": HEADERS["User-Agent"]})
        r.raise_for_status()
        root = ET.fromstring(r.text)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        for url_el in root.findall("sm:url", ns):
            loc = url_el.find("sm:loc", ns)
            if loc is not None and "/blog/" in (loc.text or ""):
                parts = loc.text.rstrip("/").split("/blog/")
                if len(parts) == 2 and parts[1]:
                    sitemap_slugs.append(parts[1])
    except Exception as e:
        print(f"  [WARN] deepseek.ai sitemap: {e}")

    # Jina listing → titles, dates, descriptions
    try:
        r = httpx.get(JINA_URL, timeout=30, headers=HEADERS)
        r.raise_for_status()
        text = r.text
    except Exception as e:
        print(f"  [FETCH ERROR] deepseek.ai blog: {e}")
        return []

    seen: set[str] = set()
    articles: list[dict] = []

    for m in _ENTRY.finditer(text):
        date_raw = m.group(1).strip()
        title    = m.group(2).strip()
        summary  = m.group(3).strip()

        url = _find_url(title, sitemap_slugs)
        if url in seen:
            continue
        seen.add(url)

        articles.append({
            "title":   title,
            "url":     url,
            "date":    _parse_date(date_raw),
            "summary": summary,
        })

    print(f"  [DeepSeek.ai] {len(articles)} article(s) found.")
    return articles[:30]
