"""
Adaptateur OpenAI / compatible (ChatGPT).

Fonctionnel dès qu'OPENAI_API_KEY est présent. Compatible avec tout endpoint au
format OpenAI (OpenRouter, groupes locaux) via OPENAI_BASE_URL. Aucune clé n'est
journalisée. Le fournisseur ne lève jamais : toute erreur devient un
ProviderResult vide, pour ne pas casser le consensus.
"""

from __future__ import annotations

import os

from ..models import ProviderResult
from .base import Provider

_INSTRUCTION = (
    "Réponds à la question de l'utilisateur comme un assistant grand public, en "
    "citant les entreprises ou produits pertinents et leurs sites quand tu les "
    "connais. Sois concret."
)


class OpenAIProvider(Provider):
    name = "openai"
    env_key = "OPENAI_API_KEY"

    def __init__(self, model: str | None = None):
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        self.base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")

    async def interroger(self, query: str, *, marque: str, domaine: str,
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
                    return self._vide(query, f"HTTP {r.status}")
                data = await r.json()
                texte = data["choices"][0]["message"]["content"]
        except Exception as e:  # réseau, JSON, clé absente : on ne casse rien
            return self._vide(query, str(e)[:80])
        return self._analyser_reponse(texte, marque, domaine, query, self.name)

    def _vide(self, query: str, motif: str) -> ProviderResult:
        return ProviderResult(provider=self.name, query=query, brand_mentioned=False,
                              brand_recommended=False, domain_cited=False,
                              raw_excerpt=f"[erreur {self.name}: {motif}]")
