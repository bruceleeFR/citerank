"""
AI provider abstraction.

Spec weakness #3: NEVER hardcode a provider's logic across the codebase. Each
engine (OpenAI, Anthropic, Gemini, Perplexity, OpenRouter) is an adapter that
implements this interface. The visibility engine only knows `Provider`, never a
specific provider.

Keys come EXCLUSIVELY from the environment (point 31) — never from code, never
from logs.
"""

from __future__ import annotations

import abc
import os

from ..models import ProviderResult


class Provider(abc.ABC):
    """Common contract for every queried AI engine."""

    #: short name, used as the key in results
    name: str = "base"
    #: environment variable holding the key
    env_key: str = ""

    def available(self) -> bool:
        """A provider is available if its key is present in the environment."""
        return bool(self.env_key and os.environ.get(self.env_key))

    @abc.abstractmethod
    async def query(self, query: str, *, brand: str, domain: str,
                    session) -> ProviderResult:
        """
        Ask `query` to the engine and analyze the answer for whether the brand is
        mentioned, recommended, cited, at what rank, and against which
        competitors. Always returns a ProviderResult — never raises: a provider
        outage must not break the consensus.
        """
        raise NotImplementedError

    # -- Shared answer analysis --------------------------------------------
    @staticmethod
    def _analyze_response(text: str, brand: str, domain: str,
                          query: str, provider: str) -> ProviderResult:
        """
        Shared extraction: does the answer contain the brand, the domain, at what
        rank. Deliberately simple and transparent — we prefer a readable, honest
        heuristic over a black box that would inflate the numbers.
        """
        low = text.lower()
        b = brand.lower()
        d = domain.lower().removeprefix("www.")

        mentioned = bool(b) and b in low
        cited = d in low
        # "recommended": the brand appears in a recommendation phrasing.
        recommended = mentioned and any(
            pattern in low for pattern in (
                f"recommend {b}", f"i recommend {b}", f"{b} is a good",
                f"use {b}", f"try {b}", f"best option is {b}", f"i'd suggest {b}",
            )
        )
        position = low.find(b) if mentioned else None
        return ProviderResult(
            provider=provider, query=query,
            brand_mentioned=mentioned, brand_recommended=recommended,
            domain_cited=cited,
            citation_url=domain if cited else "",
            position=position,
            raw_excerpt=text[:400],
        )
