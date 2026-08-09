"""
OpenAI / compatible (ChatGPT) adapter.

Works as soon as OPENAI_API_KEY is present. Compatible with any OpenAI-format
endpoint (OpenRouter, local clusters) via OPENAI_BASE_URL. No key is logged. The
provider never raises: any error becomes an empty ProviderResult, so it doesn't
break the consensus.
"""

from __future__ import annotations

import os

from ..models import ProviderResult
from .base import Provider

_INSTRUCTION = (
    "Answer the user's question like a consumer assistant, naming the relevant "
    "companies or products and their websites when you know them. Be concrete."
)


class OpenAIProvider(Provider):
    name = "openai"
    env_key = "OPENAI_API_KEY"

    def __init__(self, model: str | None = None):
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        self.base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")

    async def query(self, query: str, *, brand: str, domain: str,
                    session) -> ProviderResult:
        try:
            async with session.post(
                f"{self.base}/chat/completions",
                headers={"Authorization": f"Bearer {os.environ[self.env_key]}"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": _INSTRUCTION},
                        {"role": "user", "content": query},
                    ],
                    "temperature": 0.7,
                },
            ) as r:
                if r.status != 200:
                    return self._empty(query, f"HTTP {r.status}")
                data = await r.json()
                text = data["choices"][0]["message"]["content"]
        except Exception as e:  # network, JSON, missing key: break nothing
            return self._empty(query, str(e)[:80])
        return self._analyze_response(text, brand, domain, query, self.name)

    def _empty(self, query: str, reason: str) -> ProviderResult:
        return ProviderResult(provider=self.name, query=query, brand_mentioned=False,
                              brand_recommended=False, domain_cited=False,
                              raw_excerpt=f"[{self.name} error: {reason}]")
