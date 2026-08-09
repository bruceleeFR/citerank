"""
Deterministic mock provider.

It talks to no network: it builds a reproducible answer from the hash of
(query, brand). Two uses, both important:

  - unit tests run without a key and without network (point 26);
  - a full-flow demonstration is possible offline, without burning a cent of API.

It must NEVER be used to produce a real visibility report: its fake nature is
displayed everywhere it appears.
"""

from __future__ import annotations

import hashlib

from ..models import ProviderResult
from .base import Provider


class MockProvider(Provider):
    name = "mock"
    env_key = ""  # always available, no key required

    def available(self) -> bool:
        return True

    async def query(self, query: str, *, brand: str, domain: str,
                    session=None) -> ProviderResult:
        seed = int(hashlib.sha256(f"{query}|{brand}".encode()).hexdigest(), 16)
        mentioned = (seed % 10) < 6          # ~60% of the time
        recommended = mentioned and (seed % 3) == 0
        cited = mentioned and (seed % 4) == 0
        return ProviderResult(
            provider=self.name, query=query,
            brand_mentioned=mentioned, brand_recommended=recommended,
            domain_cited=cited, citation_url=domain if cited else "",
            position=(seed % 500) if mentioned else None,
            raw_excerpt="[deterministic fake answer — reflects no real engine]",
        )
