"""Provider-agnostic LLM text completion.

Select a provider with ``LLM_PROVIDER`` (anthropic | openai | gemini) and an
optional ``LLM_MODEL``. If no provider key is configured, ``complete`` returns
``None`` and callers fall back to deterministic templates, so the pipeline
still produces a briefing without any LLM.
"""
from __future__ import annotations

import logging

from .config import env
from .http import post_json

log = logging.getLogger(__name__)

DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-5-5",
    "openai": "gpt-4.1-mini",
    "gemini": "gemini-2.5-flash",
}
KEY_VARS = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY"}


def provider() -> str | None:
    chosen = (env("LLM_PROVIDER") or "").lower()
    if chosen:
        return chosen if env(KEY_VARS.get(chosen)) else None
    for name, var in KEY_VARS.items():  # first configured provider wins
        if env(var):
            return name
    return None


def complete(prompt: str, *, system: str = "", max_tokens: int = 4000,
             temperature: float = 0.4) -> str | None:
    name = provider()
    if not name:
        log.warning("No LLM provider configured; using template fallback.")
        return None
    model = env("LLM_MODEL") or DEFAULT_MODELS[name]
    key = env(KEY_VARS[name])
    try:
        if name == "anthropic":
            data = post_json(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
                json={"model": model, "max_tokens": max_tokens, "temperature": temperature,
                      "system": system, "messages": [{"role": "user", "content": prompt}]},
            )
            return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        if name == "openai":
            data = post_json(
                "https://api.openai.com/v1/responses",
                headers={"Authorization": f"Bearer {key}"},
                json={"model": model, "instructions": system, "input": prompt,
                      "max_output_tokens": max_tokens, "temperature": temperature},
            )
            return openai_text(data)
        if name == "gemini":
            data = post_json(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                headers={"x-goog-api-key": key},
                json={"systemInstruction": {"parts": [{"text": system}]},
                      "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                      "generationConfig": {"maxOutputTokens": max_tokens, "temperature": temperature}},
            )
            return gemini_text(data)
    except Exception as exc:  # never let the LLM take the whole run down
        log.error("LLM call failed (%s): %s", name, exc)
        return None
    raise ValueError(f"Unsupported LLM_PROVIDER '{name}'")


def openai_text(data: dict) -> str:
    parts = []
    for item in data.get("output", []):
        for c in item.get("content", []) or []:
            if c.get("type") == "output_text":
                parts.append(c.get("text", ""))
    return "".join(parts)


def gemini_text(data: dict) -> str:
    cands = data.get("candidates") or [{}]
    return "".join(p.get("text", "") for p in cands[0].get("content", {}).get("parts", []))
