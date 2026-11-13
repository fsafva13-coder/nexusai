"""Provider-agnostic async LLM client.

Supports Groq, Google Gemini, OpenRouter and Anthropic over plain HTTPS (httpx),
with the guard-rails a free tier needs: a requests-per-minute and tokens-per-minute
budget, bounded retries, and a circuit breaker. When the budget or breaker says
"no", callers fall back to the rule-based policy, so the simulation never stalls.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from collections import deque
from typing import TYPE_CHECKING, Deque, Optional, Tuple

import httpx

if TYPE_CHECKING:  # avoid a hard import cycle with the top-level config module
    from config import Settings


class LLMError(Exception):
    pass


class RateLimited(LLMError):
    def __init__(self, retry_after: float):
        super().__init__(f"rate limited, retry after {retry_after:.0f}s")
        self.retry_after = retry_after


def extract_json(text: str):
    """Return the first JSON object/array in an LLM reply (tolerates ``` fences and chatter)."""
    if not text:
        raise ValueError("empty reply")
    t = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", t, re.S)
    if fence:
        t = fence.group(1).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    starts = [i for i in (t.find("{"), t.find("[")) if i != -1]
    if not starts:
        raise ValueError("no JSON found")
    start = min(starts)
    opener = t[start]
    closer = "}" if opener == "{" else "]"
    depth, in_str, esc = 0, False, False
    for i in range(start, len(t)):
        c = t[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == opener:
            depth += 1
        elif c == closer:
            depth -= 1
            if depth == 0:
                return json.loads(t[start:i + 1])
    raise ValueError("unterminated JSON")


class LLMClient:
    def __init__(self, provider: str, model: str, api_key: Optional[str],
                 rpm: int = 20, tpm: int = 5000, timeout: float = 25.0):
        self.provider = provider
        self.model = model
        self._key = api_key
        self.rpm = rpm
        self.tpm = tpm
        self.timeout = timeout
        self._http: Optional[httpx.AsyncClient] = None
        self._calls: Deque[Tuple[float, int]] = deque()
        self._fail_streak = 0
        self._open_until = 0.0
        self.last_error: Optional[str] = None
        self.stats = {"calls": 0, "errors": 0, "tokens": 0, "latency_ms": 0.0}

    @classmethod
    def from_settings(cls, s: "Settings") -> Optional["LLMClient"]:
        if s.provider == "none" or not s.api_key:
            return None
        return cls(s.provider, s.model, s.api_key, s.llm_rpm, s.llm_tpm, s.llm_timeout)

    # --- budget ------------------------------------------------------------------------
    @property
    def available(self) -> bool:
        return self.provider != "none" and bool(self._key)

    def _prune(self, now: float) -> None:
        while self._calls and now - self._calls[0][0] > 60:
            self._calls.popleft()

    def can_call(self, est_tokens: int = 1500) -> bool:
        now = time.monotonic()
        if not self.available or now < self._open_until:
            return False
        self._prune(now)
        if len(self._calls) >= self.rpm:
            return False
        return sum(t for _, t in self._calls) + est_tokens <= self.tpm

    def _record(self, tokens: int, latency_ms: float, ok: bool) -> None:
        now = time.monotonic()
        self._calls.append((now, tokens))
        self.stats["calls"] += 1
        if ok:
            self.stats["tokens"] += tokens
            self.stats["latency_ms"] += latency_ms
            self._fail_streak = 0
        else:
            self.stats["errors"] += 1
            self._fail_streak += 1
            if self._fail_streak >= 3:
                self._open_until = now + min(300.0, 30.0 * 2 ** (self._fail_streak - 3))

    def describe(self) -> dict:
        calls_ok = max(1, self.stats["calls"] - self.stats["errors"])
        return {
            "provider": self.provider,
            "model": self.model,
            "calls": self.stats["calls"],
            "errors": self.stats["errors"],
            "tokens": self.stats["tokens"],
            "avg_latency_ms": round(self.stats["latency_ms"] / calls_ok),
            "breaker_open": time.monotonic() < self._open_until,
            "last_error": self.last_error,
        }

    # --- public API ----------------------------------------------------------------------
    async def chat_json(self, system: str, user: str, max_tokens: int = 700):
        last_exc: Optional[Exception] = None
        for attempt in range(2):
            started = time.monotonic()
            try:
                text, tokens = await self._request(system, user, max_tokens)
                data = extract_json(text)
            except RateLimited as exc:
                self._record(0, 0, False)
                self._open_until = max(self._open_until, time.monotonic() + min(60.0, exc.retry_after))
                self.last_error = str(exc)
                raise
            except (httpx.HTTPError, LLMError, ValueError, KeyError, IndexError, TypeError) as exc:
                self._record(0, 0, False)
                self.last_error = f"{type(exc).__name__}: {exc}"[:200]
                last_exc = exc
                if attempt == 0 and self.can_call(0):
                    await asyncio.sleep(0.4)
                    continue
                break
            else:
                self._record(tokens, (time.monotonic() - started) * 1000, True)
                self.last_error = None
                return data
        raise LLMError(str(last_exc) if last_exc else "LLM call failed")

    async def aclose(self) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    # --- providers -----------------------------------------------------------------------------
    def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=self.timeout)
        return self._http

    @staticmethod
    def _check(resp: httpx.Response) -> None:
        if resp.status_code == 429:
            try:
                wait = float(resp.headers.get("retry-after", 20))
            except ValueError:
                wait = 20.0
            raise RateLimited(wait)
        if resp.status_code >= 400:
            raise LLMError(f"HTTP {resp.status_code}: {resp.text[:160]}")

    async def _request(self, system: str, user: str, max_tokens: int) -> Tuple[str, int]:
        est = (len(system) + len(user)) // 3 + max_tokens // 2
        client = self._client()

        if self.provider in ("groq", "openrouter"):
            if self.provider == "groq":
                url = "https://api.groq.com/openai/v1/chat/completions"
            else:
                url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {"Authorization": f"Bearer {self._key}"}
            payload = {
                "model": self.model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "temperature": 0.7,
                "max_tokens": max_tokens,
            }
            if "gpt-oss" in self.model:
                # reasoning models spend tokens "thinking" before the JSON; keep that short
                # and leave headroom so the answer is never cut off mid-object
                payload["reasoning_effort"] = "low"
                payload["max_tokens"] = max_tokens + 800
            if self.provider == "groq":
                payload["response_format"] = {"type": "json_object"}
            else:
                headers["X-Title"] = "NexusAI"
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code == 400 and "response_format" in payload and "json_validate_failed" in resp.text:
                # strict JSON mode rejected the reply: retry once in plain mode, extract_json() copes
                payload.pop("response_format")
                resp = await client.post(url, json=payload, headers=headers)
            self._check(resp)
            body = resp.json()
            text = body["choices"][0]["message"].get("content") or ""
            return text, int((body.get("usage") or {}).get("total_tokens") or est)

        if self.provider == "gemini":
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
            generation = {"temperature": 0.7, "maxOutputTokens": max_tokens, "responseMimeType": "application/json"}
            if "flash" in self.model:
                generation["thinkingConfig"] = {"thinkingBudget": 0}
            payload = {
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": generation,
            }
            resp = await client.post(url, json=payload, headers={"x-goog-api-key": self._key or ""})
            self._check(resp)
            body = resp.json()
            text = "".join(p.get("text", "") for p in body["candidates"][0]["content"]["parts"])
            return text, int((body.get("usageMetadata") or {}).get("totalTokenCount") or est)

        if self.provider == "anthropic":
            payload = {
                "model": self.model,
                "max_tokens": max_tokens,
                "temperature": 0.7,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            }
            headers = {"x-api-key": self._key or "", "anthropic-version": "2023-06-01"}
            resp = await client.post("https://api.anthropic.com/v1/messages", json=payload, headers=headers)
            self._check(resp)
            body = resp.json()
            text = "".join(b.get("text", "") for b in body["content"] if b.get("type") == "text")
            usage = body.get("usage") or {}
            return text, int((usage.get("input_tokens") or 0) + (usage.get("output_tokens") or 0)) or est

        raise LLMError(f"unsupported provider {self.provider}")