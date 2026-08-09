"""
Provider registry. The Gemini, Perplexity and OpenRouter adapters follow the
same contract as base.Provider; OpenRouter already works via OpenAIProvider by
pointing OPENAI_BASE_URL at its endpoint.
"""

from .anthropic_provider import AnthropicProvider
from .base import Provider
from .mock import MockProvider
from .openai_provider import OpenAIProvider

# Gemini and Perplexity follow the same contract; to be added when a key is
# available to test them for real. We never register a stub that would lie about
# its availability.
_CLASSES = [OpenAIProvider, AnthropicProvider]


def available_providers() -> list[Provider]:
    """Return the providers whose key is present in the environment."""
    available = []
    for cls in _CLASSES:
        p = cls()
        if p.available():
            available.append(p)
    return available


__all__ = [
    "AnthropicProvider",
    "MockProvider",
    "OpenAIProvider",
    "Provider",
    "available_providers",
]
