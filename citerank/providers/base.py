"""
Abstraction de fournisseur IA.

Faiblesse n°3 du cahier des charges : ne JAMAIS coder en dur la logique d'un
fournisseur dans tout le code. Chaque moteur (OpenAI, Anthropic, Gemini,
Perplexity, OpenRouter) est un adaptateur qui implémente cette interface. Le
moteur de visibilité ne connaît que `Provider`, jamais un fournisseur précis.

Les clés viennent EXCLUSIVEMENT de l'environnement (point 31) — jamais du code,
jamais des journaux.
"""

from __future__ import annotations

import abc
import os

from ..models import ProviderResult


class Provider(abc.ABC):
    """Contrat commun à tous les moteurs IA interrogés."""

    #: nom court, sert de clé dans les résultats
    name: str = "base"
    #: variable d'environnement portant la clé
    env_key: str = ""

    def disponible(self) -> bool:
        """Un fournisseur est disponible si sa clé est présente dans l'environnement."""
        return bool(self.env_key and os.environ.get(self.env_key))

    @abc.abstractmethod
    async def interroger(self, query: str, *, marque: str, domaine: str,
                         session) -> ProviderResult:
        """
        Pose `query` au moteur et analyse la réponse pour dire si la marque est
        mentionnée, recommandée, citée, à quel rang, et face à quels concurrents.
        Retourne toujours un ProviderResult — jamais d'exception qui remonte :
        un fournisseur en panne ne doit pas casser le consensus.
        """
        raise NotImplementedError

    # -- Analyse partagée de la réponse ------------------------------------
    @staticmethod
    def _analyser_reponse(texte: str, marque: str, domaine: str,
                          query: str, provider: str) -> ProviderResult:
        """
        Extraction commune : présente-t-elle la marque, le domaine, à quel rang.
        Volontairement simple et transparente — on préfère une heuristique
        lisible et honnête à une boîte noire qui gonflerait les chiffres.
        """
        bas = texte.lower()
        m = marque.lower()
        d = domaine.lower().removeprefix("www.")

        mentionnee = bool(m) and m in bas
        cite = d in bas
        # « recommandé » : la marque apparaît dans une tournure de recommandation.
        recommande = mentionnee and any(
            motif in bas for motif in (
                f"recommande {m}", f"recommend {m}", f"{m} est un bon",
                f"{m} is a good", f"utilisez {m}", f"use {m}", f"try {m}",
                f"best option is {m}", f"i'd suggest {m}",
            )
        )
        position = bas.find(m) if mentionnee else None
        return ProviderResult(
            provider=provider, query=query,
            brand_mentioned=mentionnee, brand_recommended=recommande,
            domain_cited=cite,
            citation_url=domaine if cite else "",
            position=position,
            raw_excerpt=texte[:400],
        )
