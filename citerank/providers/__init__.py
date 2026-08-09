"""
Registre des fournisseurs. Les adaptateurs Gemini, Perplexity et OpenRouter
suivent le même contrat que base.Provider ; OpenRouter fonctionne déjà via
OpenAIProvider en pointant OPENAI_BASE_URL sur son endpoint.
"""

from .anthropic_provider import AnthropicProvider
from .base import Provider
from .mock import MockProvider
from .openai_provider import OpenAIProvider

# Gemini et Perplexity suivent le même contrat ; à ajouter quand une clé est
# disponible pour les tester en réel. On n'enregistre jamais un stub qui
# mentirait sur sa disponibilité.
_CLASSES = [OpenAIProvider, AnthropicProvider]


def fournisseurs_disponibles() -> list[Provider]:
    """Retourne les fournisseurs dont la clé est présente dans l'environnement."""
    dispo = []
    for cls in _CLASSES:
        p = cls()
        if p.disponible():
            dispo.append(p)
    return dispo


__all__ = [
    "AnthropicProvider",
    "MockProvider",
    "OpenAIProvider",
    "Provider",
    "fournisseurs_disponibles",
]
