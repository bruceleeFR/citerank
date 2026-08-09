"""
Fournisseur factice, déterministe.

Il ne parle à aucun réseau : il fabrique une réponse reproductible à partir du
hachage de (requête, marque). Deux usages, tous deux importants :

  - les tests unitaires tournent sans clé et sans réseau (point 26) ;
  - une démonstration du parcours complet est possible hors ligne, sans brûler
    un centime d'API.

Il ne doit JAMAIS servir à produire un vrai rapport de visibilité : sa nature
factice est affichée partout où il apparaît.
"""

from __future__ import annotations

import hashlib

from ..models import ProviderResult
from .base import Provider


class MockProvider(Provider):
    name = "mock"
    env_key = ""  # toujours disponible, aucune clé requise

    def disponible(self) -> bool:
        return True

    async def interroger(self, query: str, *, marque: str, domaine: str,
                         session=None) -> ProviderResult:
        graine = int(hashlib.sha256(f"{query}|{marque}".encode()).hexdigest(), 16)
        mentionnee = (graine % 10) < 6          # ~60 % du temps
        recommande = mentionnee and (graine % 3) == 0
        cite = mentionnee and (graine % 4) == 0
        return ProviderResult(
            provider=self.name, query=query,
            brand_mentioned=mentionnee, brand_recommended=recommande,
            domain_cited=cite, citation_url=domaine if cite else "",
            position=(graine % 500) if mentionnee else None,
            raw_excerpt="[réponse factice déterministe — ne reflète aucun moteur réel]",
        )
