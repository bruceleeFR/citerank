"""
Anthropic (Claude) adapter.

The second real provider: without it, the "multi-provider consensus" (point 13)
would have a single voice, which is no consensus. With OpenAI and Anthropic,
consistency across engines becomes measurable.

Works as soon as ANTHROPIC_API_KEY is present. No key is logged. Never raises:
any error becomes an empty result, so it doesn't break the consensus.
"""

from __future__ import annotations

import os

from ..models import ProviderResult
from .base import Provider

_INSTRUCTION = (
    "Answer the question like a consumer assistant, naming the relevant companies "
    "or products and their websites when you know them."
)


class AnthropicProvider(Provider):
    name = "anthropic"
    env_key = "ANTHROPIC_API_KEY"

    def __init__(self, model: str | None = None):
        self.model = model or os.environ.get("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")
        self.base = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")

    async def query(self, query: str, *, brand: str, domain: str,
                    session) -> ProviderResult:
        try:
            async with session.post(
                f"{self.base}/v1/messages",
                headers={
                    "x-api-key": os.environ[self.env_key],
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": 512,
                    "system": _INSTRUCTION,
                    "messages": [{"role": "user", "content": query}],
                },
            ) as r:
                if r.status != 200:
                    return self._empty(query, f"HTTP {r.status}")
                data = await r.json()
                blocks = data.get("content", [])
                text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        except Exception as e:
            return self._empty(query, str(e)[:80])
        return self._analyze_response(text, brand, domain, query, self.name)

    def _empty(self, query: str, reason: str) -> ProviderResult:
        return ProviderResult(provider=self.name, query=query, brand_mentioned=False,
                              brand_recommended=False, domain_cited=False,
                              raw_excerpt=f"[{self.name} error: {reason}]")
