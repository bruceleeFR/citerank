"""
Registre des fournisseurs. Les adaptateurs Gemini, Perplexity et OpenRouter
suivent le même contrat que base.Provider ; OpenRouter fonctionne déjà via
OpenAIProvider en pointant OPENAI_BASE_URL sur son endpoint.
"""

from .base import Provider
from .mock import MockProvider
from .openai_provider import OpenAIProvider

# Anthropic : adaptateur à ajouter (même contrat). Laissé hors registre tant
# que non implémenté, plutôt qu'un stub qui mentirait sur sa disponibilité.
_CLASSES = [OpenAIProvider]


def fournisseurs_disponibles() -> list[Provider]:
    """Retourne les fournisseurs dont la clé est présente dans l'environnement."""
    dispo = []
    for cls in _CLASSES:
        p = cls()
        if p.disponible():
            dispo.append(p)
    return dispo


__all__ = ["Provider", "MockProvider", "OpenAIProvider", "fournisseurs_disponibles"]
