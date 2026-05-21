import json
import re
import sqlite3
import httpx
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from queue import Queue
from tqdm import tqdm

from bs4 import BeautifulSoup

from vibefeed import llm
from vibefeed.sources import get_fetcher, get_fetcher_name, should_fetch_content

DB_PATH       = str(llm.ROOT_DIR / "vibefeed.db")
URL_LIST_PATH = str(llm.ROOT_DIR / "url_list.md")

HEADERS = {"User-Agent": "AIFeed-personal/1.0 (personal AI news aggregator; not for redistribution)"}

SUMMARY_PROMPT = llm.load_prompt("summary")

_tags_cfg   = llm.load_config("tags")
_VALID_TAGS = set(_tags_cfg["type_tags"] + _tags_cfg["theme_tags"])



def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            url            TEXT PRIMARY KEY,
            blog_url       TEXT NOT NULL,
            title          TEXT NOT NULL,
            content_md     TEXT,
            published_date TEXT,
            is_read        INTEGER NOT NULL DEFAULT 0,
            must_read      INTEGER NOT NULL DEFAULT 0,
            score          INTEGER,
            tags           TEXT NOT NULL DEFAULT ''
        )
    """)
    # Migrate existing DB if columns are missing
    for col in [
        "ALTER TABLE articles ADD COLUMN must_read INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE articles ADD COLUMN score INTEGER",
        "ALTER TABLE articles ADD COLUMN tags TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE articles ADD COLUMN read_time INTEGER",
    ]:
        try:
            conn.execute(col)
        except Exception:
            pass
    conn.commit()


def parse_urls(path: str) -> list[str]:
    with open(path, "r", encoding="utf-8") as f:
        return re.findall(r"https?://[^\s\)\]>\"']+", f.read())


def fetch_raw(url: str) -> str:
    for attempt in range(4):
        try:
            r = httpx.get(url, timeout=30, follow_redirects=True, headers=HEADERS)
            if r.status_code == 429:
                wait = 2 ** attempt
                print(f"  [429] Rate limited — retrying in {wait}s")
                time.sleep(wait)
                continue
            if r.status_code == 403:
                note = "expected for openai.com" if "openai.com" in url else "Cloudflare?"
                print(f"  [403] {url[:80]} — skipping content ({note})")
                return ""
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()
            return soup.get_text(separator="\n", strip=True)
        except Exception as e:
            print(f"  [FETCH ERROR] {url}: {e}")
            return ""
    print(f"  [FETCH ERROR] Gave up after retries: {url[:60]}")
    return ""



def _fix_json(raw: str) -> str:
    """Fix common LLM JSON generation issues."""
    # Fix invalid backslash escapes (e.g. LaTeX \mathbf → \\mathbf)
    raw = re.sub(r'\\(?!["\\/bfnrtu0-9])', r'\\\\', raw)
    return raw


def _parse_summary(response: str) -> tuple[str, str, int, int]:
    """Returns (bullets_md, tags_csv, major, score)."""
    raw = response.strip()
    # strip optional ```json ... ``` fences
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL).strip()
    # try strict parse, then with backslash fix
    data = None
    for candidate in (raw, _fix_json(raw)):
        try:
            data = json.loads(candidate)
            break
        except json.JSONDecodeError:
            continue
    if data is None:
        return "", "", 0, 3

    bullets = [str(b) for b in data.get("bullets", []) if b][:3]
    content_md = "\n".join(f"• {b}" for b in bullets)

    raw_tags = [t for t in data.get("tags", []) if t in _VALID_TAGS]
    tags_csv = ",".join(raw_tags[:3])

    major = 1 if data.get("major") is True else 0
    score = int(data["score"]) if isinstance(data.get("score"), (int, float)) else 3
    score = max(1, min(5, score))
    return content_md, tags_csv, major, score


_MAX_ARTICLE_CHARS = llm.max_input_chars(SUMMARY_PROMPT, reserved_output=250)


def summarize(raw_text: str) -> tuple[str, str, int, int]:
    """Returns (bullets_md, tags_csv, major, score)."""
    try:
        with _llm_sem:
            response = llm.chat(SUMMARY_PROMPT, raw_text[:_MAX_ARTICLE_CHARS])
        return _parse_summary(response)
    except Exception as e:
        print(f"  [SUMMARY ERROR] {e}")
        return "", "", 0, 3


_log_lock = threading.Lock()
_llm_sem = threading.Semaphore(1)  # one LLM call at a time — ollama is the bottleneck


def _log(msg: str) -> None:
    with _log_lock:
        print(msg, flush=True)


def _fetch_feed(blog_url: str, existing_urls: set, index: int, total: int) -> list[dict]:
    fetcher = get_fetcher(blog_url)
    method = get_fetcher_name(blog_url)
    _log(f"[{index}/{total}] {blog_url}  ({method})")

    articles = fetcher(blog_url, None)
    candidates = [
        {**a, "_blog_url": blog_url}
        for a in articles
        if a.get("title", "").strip()
        and a.get("url", "").strip()
        and a.get("date", date.today().isoformat()) >= (date.today() - timedelta(days=30)).isoformat()
        and a["url"].strip() not in existing_urls
    ]
    _log(f"  {len(articles)} in feed, {len(candidates)} new")
    return candidates


def _fetch_article_content(article: dict) -> tuple:
    url = article["url"].strip()
    title = article["title"].strip()
    blog_url = article["_blog_url"]
    published_date = article.get("date", date.today().isoformat())
    raw = fetch_raw(url) if should_fetch_content(blog_url) else ""
    rss_summary = article.get("summary", "")
    if raw:
        read_time = max(1, round(len(raw.split()) / 200))
        content_md, tags, major, score = summarize(raw)
    elif rss_summary:
        read_time = None
        content_md, tags, major, score = summarize(rss_summary)
    else:
        read_time = None
        content_md, tags, major, score = "", "", 0, 3
    return (url, blog_url, title, content_md, published_date, tags, major, score, read_time)


def _process_site_articles(site_candidates: list[dict], queue: Queue) -> None:
    try:
        for article in site_candidates:
            queue.put(_fetch_article_content(article))
    finally:
        queue.put(None)


def ingest() -> None:
    if not llm.ensure_ready():
        return

    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    blog_urls = parse_urls(URL_LIST_PATH)
    total = len(blog_urls)
    print(f"Starting ingestion — {total} source(s) | backend: {llm.backend()}\n")

    existing_urls = {row[0] for row in conn.execute("SELECT url FROM articles")}

    # Phase 1 : fetch tous les feeds en parallèle
    print("Phase 1 — fetching feeds...")
    all_candidates: list[dict] = []
    with ThreadPoolExecutor(max_workers=total) as pool:
        futures = {
            pool.submit(_fetch_feed, url, existing_urls, i, total): url
            for i, url in enumerate(blog_urls, 1)
        }
        for future in as_completed(futures):
            all_candidates.extend(future.result())

    # Regroupe par site pour respecter la règle "séquentiel par site"
    by_site: dict[str, list[dict]] = defaultdict(list)
    for a in all_candidates:
        by_site[a["_blog_url"]].append(a)

    # Phase 2 : fetch contenu — un thread par site, barre tqdm sur le thread principal
    print(f"\nPhase 2 — fetching & summarizing {len(all_candidates)} article(s)...")
    total_new = 0
    queue: Queue = Queue()
    n_sites = len(by_site)

    with ThreadPoolExecutor(max_workers=n_sites) as pool:
        for candidates in by_site.values():
            pool.submit(_process_site_articles, candidates, queue)

        with tqdm(total=len(all_candidates), unit="article") as pbar:
            sites_done = 0
            while sites_done < n_sites:
                row = queue.get()
                if row is None:
                    sites_done += 1
                    continue
                conn.execute(
                    "INSERT OR IGNORE INTO articles (url, blog_url, title, content_md, published_date, is_read, tags, must_read, score, read_time) VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?)",
                    row,
                )
                conn.commit()
                total_new += 1
                pbar.update(1)

    conn.close()
    print(f"\nDone — {total_new} new article(s) added across {total} source(s).")


if __name__ == "__main__":
    ingest()
