import sqlite3
from contextlib import asynccontextmanager
from datetime import date, timedelta
from fastapi import FastAPI, Request, Form, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, Response
import markdown as md
from vibefeed import llm

DB_PATH = str(llm.ROOT_DIR / "vibefeed.db")
PAGE_SIZE = 50

DIGEST_PROMPT = llm.load_prompt("digest")
_tags_cfg     = llm.load_config("tags")
TYPE_TAGS     = set(_tags_cfg["type_tags"])

@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = sqlite3.connect(DB_PATH)
    for stmt in [
        "ALTER TABLE articles ADD COLUMN must_read INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE articles ADD COLUMN score INTEGER",
        "ALTER TABLE articles ADD COLUMN tags TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE articles ADD COLUMN read_time INTEGER",
        """CREATE TABLE IF NOT EXISTS digests (
            week         TEXT PRIMARY KEY,
            content_md   TEXT NOT NULL,
            generated_at TEXT NOT NULL
        )""",
    ]:
        try:
            conn.execute(stmt)
        except Exception:
            pass
    conn.commit()
    conn.close()
    yield


app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory=str(llm.ROOT_DIR / "templates"))


SOURCE_GROUPS: list[tuple[str, list[str]]] = [
    ("Chercheurs", ["bair.berkeley", "cameronrwolfe", "crfm.stanford", "hazyresearch", "karpathy", "lilianweng", "languagemodels", "mlhonk", "sebastianraschka", "timdettmers", "tridao"]),
    ("MLOps",      ["eugeneyan", "huyenchip", "interconnects", "oxen.ai", "philschmid", "simonwillison"]),
    ("Infra",      ["anyscale", "modal.com", "nvidia", "pytorch", "semianalysis", "together.ai", "vllm.ai"]),
    ("Labs",       ["anthropic", "ai.meta.com", "deepmind", "deepseek.ai", "ernie.baidu", "huggingface", "kimi.com", "machinelearning.apple", "microsoft.com", "mistral", "openai", "qwen.ai"]),
]


def group_sources(sources: list[str]) -> list[tuple[str, list[str]]]:
    used: set[str] = set()
    result = []
    for group_name, patterns in SOURCE_GROUPS:
        group = sorted(
            [s for s in sources if any(p in s for p in patterns)],
            key=lambda s: source_style(s)[2],
        )
        if group:
            result.append((group_name, group))
            used.update(group)
    ungrouped = sorted([s for s in sources if s not in used], key=lambda s: source_style(s)[2])
    if ungrouped:
        result.append(("Autres", ungrouped))
    return result


SOURCE_STYLES: dict[str, tuple[str, str, str, str | None]] = {
    "anthropic":        ("badge-orange",  "border-t-orange-400",  "Anthropic",      "https://www.anthropic.com/favicon.ico"),
    "openai":           ("badge-emerald", "border-t-emerald-400", "OpenAI",         "https://openai.com/favicon.ico"),
    "huggingface.co/blog":   ("badge-yellow",  "border-t-yellow-400",  "HuggingFace",    "https://huggingface.co/favicon.ico"),
    "ai.meta.com":      ("badge-blue",    "border-t-blue-500",    "Meta AI",        "https://ai.meta.com/favicon.ico"),
    "microsoft.com":    ("badge-sky",     "border-t-sky-500",     "MSR",            "https://www.microsoft.com/favicon.ico"),
    "machinelearning.apple.com": ("badge-gray", "border-t-gray-300", "Apple ML",    "https://machinelearning.apple.com/favicon.ico"),
    "mistral":          ("badge-orange",  "border-t-orange-400",  "Mistral",        "https://mistral.ai/favicon.ico"),
    "qwen.ai":          ("badge-violet",  "border-t-violet-500",  "Qwen",           "https://www.google.com/s2/favicons?domain=qwen.ai&sz=32"),
    "deepmind":         ("badge-blue",    "border-t-blue-400",    "DeepMind",       "https://www.google.com/s2/favicons?domain=deepmind.google&sz=32"),
    "simonwillison":    ("badge-sky",     "border-t-sky-400",     "Simon Willison", None),
    "karpathy":         ("badge-red",     "border-t-red-400",     "Karpathy",       None),
    "lilianweng":       ("badge-pink",    "border-t-pink-400",    "Lilian Weng",    None),
    "sebastianraschka": ("badge-indigo",  "border-t-indigo-400",  "Raschka",        None),
    "languagemodels":   ("badge-teal",    "border-t-teal-400",    "Jay Alammar",    None),
    "huyenchip":        ("badge-rose",    "border-t-rose-400",    "Chip Huyen",     None),
    "eugeneyan":        ("badge-cyan",    "border-t-cyan-400",    "Eugene Yan",     None),
    "cameronrwolfe":    ("badge-emerald", "border-t-emerald-400", "Cameron Wolfe",  None),
    "mlhonk":           ("badge-gray",    "border-t-gray-400",    "Mlhonk",         None),
    "interconnects.ai": ("badge-purple",  "border-t-purple-400",  "Nathan Lambert", None),
    "tridao":           ("badge-rose",    "border-t-rose-400",    "Tri Dao",        None),
    "timdettmers":      ("badge-indigo",  "border-t-indigo-300",  "Tim Dettmers",   None),
    "bair.berkeley":    ("badge-amber",   "border-t-amber-500",   "BAIR",           "https://bair.berkeley.edu/favicon.ico"),
    "crfm.stanford":    ("badge-red",     "border-t-red-500",     "Stanford CRFM",  None),
    "hazyresearch":     ("badge-red",     "border-t-red-400",     "Hazy Research",  None),
    "modal.com":        ("badge-violet",  "border-t-violet-400",  "Modal",          None),
    "pytorch.org":      ("badge-orange",  "border-t-orange-500",  "PyTorch",        "https://pytorch.org/wp-content/uploads/2024/10/cropped-favicon-32x32.webp"),
    "nvidia.com":       ("badge-emerald", "border-t-emerald-500", "NVIDIA",         "https://developer.nvidia.com/assets/favicon-81bff16cada05fcff11e5711f7e6212bdc2e0a32ee57cd640a8cf66c87a6cbe6.ico"),
    "vllm.ai":          ("badge-blue",    "border-t-blue-400",    "vLLM",           None),
    "philschmid":       ("badge-yellow",  "border-t-yellow-400",  "Phil Schmid",    None),
    "semianalysis":     ("badge-gray",    "border-t-gray-400",    "SemiAnalysis",   None),
    "anyscale":         ("badge-teal",    "border-t-teal-400",    "Anyscale",       None),
    "oxen.ai":          ("badge-red",     "border-t-red-400",     "Oxen AI",        "https://www.google.com/s2/favicons?domain=oxen.ai&sz=32"),
    "together.ai":      ("badge-purple",  "border-t-purple-400",  "Together AI",    None),
    "deepseek.ai":      ("badge-blue",    "border-t-blue-500",    "DeepSeek",       "https://www.google.com/s2/favicons?domain=deepseek.com&sz=32"),
    "ernie.baidu.com":  ("badge-blue",    "border-t-blue-400",    "ERNIE",          "https://www.google.com/s2/favicons?domain=ernie.baidu.com&sz=32"),
    "kimi.com":         ("badge-indigo",  "border-t-indigo-400",  "Kimi",           "https://www.google.com/s2/favicons?domain=kimi.com&sz=32"),
}


def source_style(blog_url: str) -> tuple[str, str, str, str | None]:
    for key, val in SOURCE_STYLES.items():
        if key in blog_url:
            return val
    domain = blog_url.split("//")[-1].split("/")[0].replace("www.", "")
    return "badge-gray", "border-t-gray-400", domain, None


templates.env.globals["source_style"] = source_style


def parse_tldr(content_md: str) -> list[str]:
    if not content_md:
        return []
    bullets = [
        line.lstrip("•-* ").strip()
        for line in content_md.splitlines()
        if line.strip().startswith(("•", "-", "*")) and len(line.strip()) > 3
    ]
    return (bullets or [content_md[:180].strip()])[:3]


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _build_query(source: list[str], unread: bool, must_read: bool) -> tuple[str, list]:
    query = "SELECT * FROM articles"
    params: list = []
    filters = []
    if source:
        placeholders = ",".join(["?"] * len(source))
        filters.append(f"blog_url IN ({placeholders})")
        params.extend(source)
    if unread:
        filters.append("is_read = 0")
    if must_read:
        filters.append("must_read = 1")
    filters.append("(score IS NULL OR score >= 2)")
    if filters:
        query += " WHERE " + " AND ".join(filters)
    query += " ORDER BY published_date DESC"
    return query, params


def _build_articles(rows) -> list[dict]:
    articles = []
    for r in rows:
        css, border, label, logo = source_style(r["blog_url"])
        articles.append({
            "url":            r["url"],
            "blog_url":       r["blog_url"],
            "title":          r["title"],
            "published_date": r["published_date"],
            "is_read":        r["is_read"],
            "must_read":      r["must_read"],
            "score":          r["score"],
            "tags":           [t for t in r["tags"].split(",") if t] if r["tags"] else [],
            "tldr":           parse_tldr(r["content_md"]),
            "source_css":     css,
            "source_border":  border,
            "source_label":   label,
            "source_logo":    logo,
            "read_time":      r["read_time"],
            "date_label":     date_label(r["published_date"]),
        })
    return articles


_MONTHS_FR = ["janvier","février","mars","avril","mai","juin","juillet","août","septembre","octobre","novembre","décembre"]

def date_label(iso: str) -> str:
    try:
        d = date.fromisoformat(iso)
    except (ValueError, TypeError):
        return iso or ""
    today = date.today()
    if d == today:
        return "Aujourd'hui"
    if d == today - timedelta(days=1):
        return "Hier"
    return f"{d.day} {_MONTHS_FR[d.month - 1]} {d.year}"


def current_week() -> str:
    return date.today().strftime("%G-W%V")


# ── Main feed ─────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, source: list[str] = Query(default=[]), unread: bool = False, must_read: bool = False):
    conn = get_conn()
    sources = [r["blog_url"] for r in conn.execute(
        "SELECT DISTINCT blog_url FROM articles ORDER BY blog_url"
    )]
    query, params = _build_query(source, unread, must_read)
    total = conn.execute(f"SELECT COUNT(*) FROM ({query})", params).fetchone()[0]
    rows = conn.execute(query + f" LIMIT {PAGE_SIZE}", params).fetchall()
    if not (unread or must_read or source):
        unread_count = conn.execute(
            "SELECT COUNT(*) FROM articles WHERE is_read = 0 AND (score IS NULL OR score >= 2)"
        ).fetchone()[0]
    conn.close()

    articles = _build_articles(rows)
    if unread or must_read or source:
        unread_count = sum(1 for a in articles if not a["is_read"])

    return templates.TemplateResponse(request, "index.html", {
        "articles":         articles,
        "grouped_sources":  group_sources(sources),
        "active_sources":   source,
        "unread_only":      unread,
        "must_read_only":   must_read,
        "total":            total,
        "unread_count":     unread_count,
        "type_tags":        TYPE_TAGS,
        "has_more":         total > PAGE_SIZE,
        "back_url":         str(request.url),
        "PAGE_SIZE":        PAGE_SIZE,
    })


@app.get("/articles/more", response_class=HTMLResponse)
async def articles_more(
    request: Request,
    offset: int = Query(default=PAGE_SIZE),
    source: list[str] = Query(default=[]),
    unread: bool = False,
    must_read: bool = False,
    prev_date: str = Query(default=""),
):
    conn = get_conn()
    query, params = _build_query(source, unread, must_read)
    rows = conn.execute(query + f" LIMIT {PAGE_SIZE} OFFSET {offset}", params).fetchall()
    total = conn.execute(f"SELECT COUNT(*) FROM ({query})", params).fetchone()[0]
    conn.close()

    articles = _build_articles(rows)
    back_url = str(request.url).split("/articles/more")[0] + "/?" + "&".join(
        f"source={s}" for s in source
    ) + ("&unread=true" if unread else "") + ("&must_read=true" if must_read else "")

    has_more = offset + PAGE_SIZE < total
    return templates.TemplateResponse(request, "_cards.html", {
        "articles":  articles,
        "type_tags": TYPE_TAGS,
        "prev_date": prev_date,
        "back_url":  back_url,
        "has_more":  has_more,
    })


@app.post("/mark-read")
async def mark_read(url: str = Form(...), back: str = Form("/")):
    conn = get_conn()
    conn.execute("UPDATE articles SET is_read = 1 WHERE url = ?", (url,))
    conn.commit()
    conn.close()
    return RedirectResponse(url=back, status_code=303)


@app.post("/mark-unread")
async def mark_unread(url: str = Form(...), back: str = Form("/")):
    conn = get_conn()
    conn.execute("UPDATE articles SET is_read = 0 WHERE url = ?", (url,))
    conn.commit()
    conn.close()
    return RedirectResponse(url=back, status_code=303)


@app.post("/toggle-must-read")
async def toggle_must_read(url: str = Form(...), back: str = Form("/")):
    conn = get_conn()
    conn.execute("UPDATE articles SET must_read = 1 - must_read WHERE url = ?", (url,))
    conn.commit()
    conn.close()
    return RedirectResponse(url=back, status_code=303)


# ── Weekly digest ──────────────────────────────────────────────────────────────

@app.get("/weekly", response_class=HTMLResponse)
async def weekly(request: Request):
    conn = get_conn()
    week = current_week()
    row = conn.execute(
        "SELECT * FROM digests WHERE week = ?", (week,)
    ).fetchone()
    conn.close()

    digest_html = md.markdown(row["content_md"], extensions=["nl2br"]) if row else None
    generated_at = row["generated_at"] if row else None

    return templates.TemplateResponse(request, "weekly.html", {
        "week":         week,
        "digest_html":  digest_html,
        "generated_at": generated_at,
    })


@app.post("/weekly/generate", response_class=HTMLResponse)
async def generate_digest(request: Request):
    conn = get_conn()
    week = current_week()
    cutoff = (date.today() - timedelta(days=7)).isoformat()

    rows = conn.execute(
        "SELECT title, blog_url, url, content_md FROM articles "
        "WHERE published_date >= ? ORDER BY published_date DESC LIMIT 40",
        (cutoff,)
    ).fetchall()

    if not rows:
        digest_html = "<p class='text-gray-400 italic'>Aucun article cette semaine.</p>"
        return templates.TemplateResponse(request, "weekly.html", {
            "week": week, "digest_html": digest_html, "generated_at": None,
        })

    articles_text = ""
    for i, r in enumerate(rows, 1):
        tldr = (r["content_md"] or "").strip()[:300]
        articles_text += f"\n[{i}] {r['title']}\nSource: {r['blog_url']}\nURL: {r['url']}\nSummary: {tldr}\n"

    content_md = llm.chat(None, DIGEST_PROMPT.replace("{articles}", articles_text), max_tokens=1500)

    now = date.today().isoformat()
    conn.execute(
        "INSERT OR REPLACE INTO digests (week, content_md, generated_at) VALUES (?, ?, ?)",
        (week, content_md, now),
    )
    conn.commit()
    conn.close()

    digest_html = md.markdown(content_md, extensions=["nl2br"])
    return templates.TemplateResponse(request, "weekly.html", {
        "week":         week,
        "digest_html":  digest_html,
        "generated_at": now,
    })
