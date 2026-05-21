import os
import subprocess
import time
from pathlib import Path
import yaml

ROOT_DIR    = Path(__file__).parent.parent
PROMPTS_DIR = ROOT_DIR / "prompts"
CONFIG_DIR  = ROOT_DIR / "config"

_config: dict | None = None


def _cfg() -> dict:
    global _config
    if _config is None:
        _config = yaml.safe_load((CONFIG_DIR / "llm.yaml").read_text(encoding="utf-8"))
    return _config


def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8").strip()


def load_config(name: str) -> dict:
    return yaml.safe_load((CONFIG_DIR / f"{name}.yaml").read_text(encoding="utf-8"))


_CHARS_PER_TOKEN = 3.5  # conservative estimate (English ~4, mixed content less)


def backend() -> str:
    return _cfg()["backend"]


_PRACTICAL_CAP = 6_000  # chars — enough for intro + key sections, beyond this quality degrades


def max_input_chars(prompt: str = "", reserved_output: int = 512) -> int:
    """Return the max safe number of input chars for the article text.

    Accounts for context window, prompt length, and reserved output tokens.
    Also enforces a practical cap so large articles don't stall the pipeline.
    Returns a large value for API backends (no hard context constraint here).
    """
    cfg = _cfg()
    if cfg["backend"] != "ollama":
        return 100_000
    ctx = cfg["ollama"].get("context_window", 4096)
    prompt_tokens = len(prompt) / _CHARS_PER_TOKEN
    safety = 150
    available = ctx - prompt_tokens - reserved_output - safety
    theoretical = max(500, int(available * _CHARS_PER_TOKEN))
    return min(theoretical, _PRACTICAL_CAP)


def ensure_ready() -> bool:
    """For ollama: start the service if not running. No-op for API backends."""
    if backend() != "ollama":
        return True
    try:
        import ollama as _ollama
        _ollama.list()
        return True
    except Exception:
        print("Ollama not running — starting service...")
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env={**os.environ, "OLLAMA_NUM_PARALLEL": "1"},
        )
        for _ in range(20):
            time.sleep(1)
            try:
                _ollama.list()
                print("Ollama ready.\n")
                return True
            except Exception:
                pass
        print("[ERROR] Ollama did not start in time.")
        return False


def chat(system: str | None, user: str, max_tokens: int = -1) -> str:
    cfg = _cfg()
    b = cfg["backend"]

    if b == "ollama":
        import ollama as _ollama
        model = cfg["ollama"]["model"]
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})
        options: dict = {"num_predict": max_tokens, "thinking": False}
        if ctx := cfg["ollama"].get("context_window"):
            options["num_ctx"] = ctx
        response = _ollama.chat(model=model, messages=messages, options=options)
        return response.message.content

    elif b == "anthropic":
        import anthropic
        model = cfg["anthropic"]["model"]
        api_key = os.environ.get("ANTHROPIC_API_KEY") or cfg["anthropic"].get("api_key")
        client = anthropic.Anthropic(api_key=api_key)
        kwargs: dict = dict(model=model, max_tokens=max_tokens, messages=[{"role": "user", "content": user}])
        if system:
            kwargs["system"] = system
        message = client.messages.create(**kwargs)
        return message.content[0].text

    elif b == "openai":
        from openai import OpenAI
        model = cfg["openai"]["model"]
        api_key = os.environ.get("OPENAI_API_KEY") or cfg["openai"].get("api_key")
        client = OpenAI(api_key=api_key)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})
        response = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=messages,
        )
        return response.choices[0].message.content

    else:
        raise ValueError(f"Unknown backend: {b!r}. Choose ollama, anthropic, or openai.")
