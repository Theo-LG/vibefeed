"""RSS/Atom fetcher — default for sources with a known feed URL."""
import feedparser
from datetime import date
from typing import Callable

FEED_MAP: dict[str, str] = {
    "huggingface.co/blog":          "https://huggingface.co/blog/feed.xml",
    "lilianweng.github.io":         "https://lilianweng.github.io/index.xml",
    "karpathy.github.io":           "https://karpathy.github.io/feed.xml",
    "magazine.sebastianraschka.com":"https://magazine.sebastianraschka.com/feed",
    "newsletter.languagemodels.co": "https://newsletter.languagemodels.co/feed",
    "simonwillison.net":            "https://simonwillison.net/atom/entries/",
    "openai.com":                   "https://openai.com/news/rss.xml",
    "google-deepmind":              "https://blog.google/innovation-and-ai/models-and-research/google-deepmind/rss/",
    "eugeneyan.com":                "https://eugeneyan.com/rss/",
    "tridao.me":                    "https://tridao.me/feed.xml",
    "bair.berkeley.edu":            "https://bair.berkeley.edu/blog/feed.xml",
    "crfm.stanford.edu":            "https://crfm.stanford.edu/feed.xml",
    "interconnects.ai":             "https://www.interconnects.ai/feed",
    "semianalysis.com":             "https://www.semianalysis.com/feed",
    "microsoft.com/en-us/research": "https://www.microsoft.com/en-us/research/blog/feed/",
    "machinelearning.apple.com":    "https://machinelearning.apple.com/rss.xml",
    "huyenchip.com":                "https://huyenchip.com/feed.xml",
    "anyscale.com":                 "https://www.anyscale.com/rss.xml",
    "timdettmers.com":              "https://timdettmers.com/feed",
    "together.ai":                  "https://www.together.ai/blog/rss.xml",
    "cameronrwolfe.substack.com":   "https://cameronrwolfe.substack.com/feed",
    "pytorch.org":                  "https://pytorch.org/blog/feed/",
    "developer.nvidia.com":         "https://developer.nvidia.com/blog/feed/",
}


def _parse_date(entry) -> str:
    # Use feedparser's pre-parsed struct_time — handles both RFC 2822 and ISO 8601
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            try:
                return date(*parsed[:3]).isoformat()
            except Exception:
                pass
    return date.today().isoformat()


def fetch(blog_url: str, extract_fn: Callable) -> list[dict]:
    feed_url = next((v for k, v in FEED_MAP.items() if k in blog_url), None)
    if not feed_url:
        print(f"  [RSS] No feed URL found for {blog_url}")
        return []

    feed = feedparser.parse(feed_url)
    if feed.bozo and not feed.entries:
        print(f"  [RSS ERROR] Could not parse {feed_url}")
        return []

    articles = [
        {
            "title": e.get("title", "").strip(),
            "url": e.get("link", "").strip(),
            "date": _parse_date(e),
            "summary": e.get("summary", "").strip(),
        }
        for e in feed.entries
        if e.get("title") and e.get("link")
    ]
    print(f"  [RSS] {len(articles)} article(s) found.")
    return articles
