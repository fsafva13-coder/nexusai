"""Runtime configuration, read from environment variables (see .env.example)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()

# Model IDs change often: every default can be overridden with LLM_MODEL.
PROVIDERS = {
    "groq": {
        "keys": ("GROQ_API_KEY",),
        "model": "llama-3.1-8b-instant",
        "rpm": 25,
        "tpm": 5500,
        "every": 6,
    },
    "gemini": {
        "keys": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        "model": "gemini-2.5-flash",
        "rpm": 9,
        "tpm": 200000,
        "every": 4,
    },
    "openrouter": {
        "keys": ("OPENROUTER_API_KEY",),
        "model": "meta-llama/llama-3.3-70b-instruct:free",
        "rpm": 15,
        "tpm": 60000,
        "every": 5,
    },
    "anthropic": {
        "keys": ("ANTHROPIC_API_KEY",),
        "model": "claude-haiku-5-5",
        "rpm": 40,
        "tpm": 40000,
        "every": 4,
    },
}
AUTO_ORDER = ("groq", "gemini", "openrouter", "anthropic")


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _find_key(provider: str) -> Optional[str]:
    for name in PROVIDERS[provider]["keys"]:
        value = os.getenv(name)
        if value:
            return value.strip()
    return None


@dataclass(frozen=True)
class Settings:
    provider: str                      # groq | gemini | openrouter | anthropic | none
    model: str
    api_key: Optional[str] = field(default=None, repr=False)
    llm_every: int = 5                 # planning round every N ticks
    llm_rpm: int = 20
    llm_tpm: int = 5000
    llm_timeout: float = 25.0
    note: str = ""
    allowed_origins: List[str] = field(default_factory=lambda: ["*"])
    max_sessions: int = 20
    max_ticks_cap: int = 300


def load_settings() -> Settings:
    requested = os.getenv("LLM_PROVIDER", "auto").strip().lower()
    provider, key, note = "none", None, ""

    if requested in ("none", "off", "heuristic", "rules"):
        note = "LLM disabled by LLM_PROVIDER; agents use the rule-based policy."
    elif requested == "auto":
        for candidate in AUTO_ORDER:
            found = _find_key(candidate)
            if found:
                provider, key = candidate, found
                break
        if provider == "none":
            note = "No API key found; agents use the rule-based policy. Add GROQ_API_KEY (free) to enable LLM agents."
    elif requested in PROVIDERS:
        found = _find_key(requested)
        if found:
            provider, key = requested, found
        else:
            note = f"LLM_PROVIDER={requested} but its API key is not set; using the rule-based policy."
    else:
        note = f"Unknown LLM_PROVIDER '{requested}'; using the rule-based policy."

    defaults = PROVIDERS.get(provider, {})
    origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()] or ["*"]

    return Settings(
        provider=provider,
        model=os.getenv("LLM_MODEL") or defaults.get("model", ""),
        api_key=key,
        llm_every=max(1, _int("LLM_EVERY", defaults.get("every", 5))),
        llm_rpm=max(1, _int("LLM_RPM", defaults.get("rpm", 20))),
        llm_tpm=max(500, _int("LLM_TPM", defaults.get("tpm", 5000))),
        llm_timeout=_float("LLM_TIMEOUT", 25.0),
        note=note,
        allowed_origins=origins,
        max_sessions=max(1, _int("MAX_SESSIONS", 20)),
        max_ticks_cap=max(10, _int("MAX_TICKS_CAP", 300)),
    )
