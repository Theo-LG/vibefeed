try:
    from .anthropic import fetch as _anthropic_fetch
    _HAS_ANTHROPIC = True
except ImportError:
    _anthropic_fetch = None
    _HAS_ANTHROPIC = False
from .jina import fetch as _jina_fetch
from .mistral import fetch as _mistral_fetch
from .modal import fetch as _modal_fetch
from .philschmid import fetch as _philschmid_fetch
from .rss import fetch as _rss_fetch
from .vllm import fetch as _vllm_fetch
from .qwen import fetch as _qwen_fetch

try:
    from .meta import fetch as _meta_fetch
    _HAS_META = True
except ImportError:
    _meta_fetch = None
    _HAS_META = False

_FETCHERS: dict[str, tuple] = {
    **({"anthropic.com": (_anthropic_fetch, "anthropic")} if _HAS_ANTHROPIC else {}),
    **({"ai.meta.com": (_meta_fetch, "meta")} if _HAS_META else {}),
    "mistral.ai":             (_mistral_fetch,   "mistral"),
    "together.ai":            (_rss_fetch,       "rss"),
    "hazyresearch.stanford":  (_jina_fetch,      "bs4"),
    "modal.com":              (_modal_fetch,      "modal"),
    "vllm.ai":                (_vllm_fetch,       "vllm"),
    "qwen.ai":                (_qwen_fetch,       "qwen"),
    "philschmid.de":          (_philschmid_fetch, "philschmid"),
}

_DEFAULT = (_rss_fetch, "rss")

_NO_FETCH = {
    "microsoft.com",         # ToS: AI services restriction
    "developer.nvidia.com",  # ToS: scraping explicitly forbidden
    "machinelearning.apple.com",  # ToS: scraping explicitly forbidden
    "openai.com",            # 403 in practice + ToS unclear
    "semianalysis.com",      # ToS: automated data collection forbidden
    "substack.com",          # ToS: scraping explicitly forbidden
    "cameronrwolfe.substack.com",
    "interconnects.ai",
    "magazine.sebastianraschka.com",
    "newsletter.languagemodels.co",
}


def get_fetcher(blog_url: str):
    for key, (fetcher, _) in _FETCHERS.items():
        if key in blog_url:
            return fetcher
    return _DEFAULT[0]


def get_fetcher_name(blog_url: str) -> str:
    for key, (_, name) in _FETCHERS.items():
        if key in blog_url:
            return name
    return _DEFAULT[1]


def should_fetch_content(blog_url: str) -> bool:
    return not any(d in blog_url for d in _NO_FETCH)
