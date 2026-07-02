"""LLM provider abstraction.

Supports Anthropic and OpenAI when a key is configured, and otherwise reports
itself as unavailable so each agent falls back to its deterministic offline
engine. This keeps the demo runnable with zero configuration while allowing an
instant upgrade to live models by setting one environment variable.
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional

from ..config import settings


class LLMClient:
    def __init__(self) -> None:
        self.provider = (settings.llm_provider or "offline").lower()
        self._client: Any = None
        self.available = False
        self.model = ""
        self._init_provider()

    def _resolve_provider(self) -> str:
        """Pick the effective provider.

        If the configured provider has a key, use it. Otherwise auto-detect any
        key that IS present so that simply pasting a key into .env turns the
        agents on, regardless of the PIP_LLM_PROVIDER setting.
        """
        if self.provider == "anthropic" and settings.anthropic_api_key:
            return "anthropic"
        if self.provider == "openai" and settings.openai_api_key:
            return "openai"
        if self.provider == "groq" and settings.groq_api_key:
            return "groq"
        if settings.anthropic_api_key:
            return "anthropic"
        if settings.openai_api_key:
            return "openai"
        if settings.groq_api_key:
            return "groq"
        return "offline"

    def _init_provider(self) -> None:
        self.provider = self._resolve_provider()
        if self.provider == "anthropic":
            try:
                import anthropic

                self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
                self.model = settings.anthropic_model
                self.available = True
            except Exception:
                self.available = False
        elif self.provider == "openai":
            try:
                from openai import OpenAI

                self._client = OpenAI(api_key=settings.openai_api_key)
                self.model = settings.openai_model
                self.available = True
            except Exception:
                self.available = False
        elif self.provider == "groq":
            # Groq exposes an OpenAI-compatible API, so reuse the OpenAI client.
            try:
                from openai import OpenAI

                self._client = OpenAI(
                    api_key=settings.groq_api_key,
                    base_url="https://api.groq.com/openai/v1",
                )
                self.model = settings.groq_model
                self.available = True
            except Exception:
                self.available = False
        else:
            self.available = False

    @property
    def label(self) -> str:
        if self.available:
            return f"{self.provider}:{self.model}"
        return "offline-deterministic-engine"

    def complete(self, system: str, prompt: str, max_tokens: int = 1500) -> str:
        if not self.available:
            raise RuntimeError("LLM client is not available (offline mode).")
        if self.provider == "anthropic":
            msg = self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
            return "".join(
                block.text for block in msg.content if getattr(block, "type", "") == "text"
            )
        # openai
        resp = self._client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        )
        return resp.choices[0].message.content or ""

    def complete_json(self, system: str, prompt: str, max_tokens: int = 1500) -> Any:
        raw = self.complete(
            system + "\nRespond with valid JSON only, no markdown fences.",
            prompt,
            max_tokens,
        )
        return _extract_json(raw)


def _extract_json(text: str) -> Any:
    text = text.strip()
    # Strip code fences if present.
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Last resort: grab first {...} or [...] block.
        match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        raise


# Singleton client used across agents.
llm = LLMClient()
