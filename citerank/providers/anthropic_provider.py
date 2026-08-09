"""
Adaptateur Anthropic (Claude).

Le deuxième vrai fournisseur : sans lui, le « consensus multi-fournisseurs »
(point 13) n'aurait qu'une seule voix, ce qui n'est pas un consensus. Avec OpenAI
et Anthropic, la constance entre moteurs devient mesurable.

Fonctionnel dès qu'ANTHROPIC_API_KEY est présent. Aucune clé journalisée. Ne lève
jamais : toute erreur devient un résultat vide, pour ne pas casser le consensus.
"""

from __future__ import annotations

import os

from ..models import ProviderResult
from .base import Provider

_INSTRUCTION = (
    "Réponds à la question comme un assistant grand public, en citant les "
    "entreprises ou produits pertinents et leurs sites quand tu les connais."
)


class AnthropicProvider(Provider):
    name = "anthropic"
    env_key = "ANTHROPIC_API_KEY"

    def __init__(self, model: str | None = None):
        self.model = model or os.environ.get("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")
        self.base = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")

    async def interroger(self, query: str, *, marque: str, domaine: str,
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
                    return self._vide(query, f"HTTP {r.status}")
                data = await r.json()
                blocs = data.get("content", [])
                texte = "".join(b.get("text", "") for b in blocs if b.get("type") == "text")
        except Exception as e:
            return self._vide(query, str(e)[:80])
        return self._analyser_reponse(texte, marque, domaine, query, self.name)

    def _vide(self, query: str, motif: str) -> ProviderResult:
        return ProviderResult(provider=self.name, query=query, brand_mentioned=False,
                              brand_recommended=False, domain_cited=False,
                              raw_excerpt=f"[erreur {self.name}: {motif}]")
