"""Adapters for vendors that speak the OpenAI chat-completions REST shape.

Groq, OpenRouter, Cerebras, and Mistral all implement the same request/response
JSON as OpenAI's ``chat.completions`` endpoint, authenticated the same way
(``Authorization: Bearer <key>``) — only the base URL, default model, and
typical cost tier differ. Each class below is therefore a thin
:class:`~.openai_provider.OpenAIProvider` subclass that fixes those three
things and lets the official ``openai`` SDK (already an optional extra) do the
actual request/response translation and error normalisation via its
``base_url`` override — no separate translation layer to maintain or drift out
of sync with the OpenAI adapter.

All four are free-tier-friendly, so :class:`~model_dispatcher.types.ModelTier`
defaults to ``CHEAP`` (matching :class:`~.gemini_provider.GeminiProvider`)
rather than ``STANDARD``/``PREMIUM``; override ``tier`` per instance if a
particular account/model should route differently.
"""

from __future__ import annotations

from ..types import ModelTier
from .openai_provider import OpenAIProvider

__all__ = [
    "GroqProvider",
    "OpenRouterProvider",
    "CerebrasProvider",
    "MistralProvider",
]


class GroqProvider(OpenAIProvider):
    """Groq's free, OpenAI-compatible, low-latency inference API."""

    _BASE_URL = "https://api.groq.com/openai/v1"
    _DEFAULT_MODEL = "openai/gpt-oss-120b"

    def __init__(
        self,
        *,
        model: str = _DEFAULT_MODEL,
        tier: ModelTier = ModelTier.CHEAP,
        api_key: str | None = None,
    ) -> None:
        super().__init__(
            model=model,
            tier=tier,
            api_key=api_key,
            base_url=self._BASE_URL,
            name=f"groq:{model}",
        )


class OpenRouterProvider(OpenAIProvider):
    """OpenRouter — one key routes to many vendors' models, several free."""

    _BASE_URL = "https://openrouter.ai/api/v1"
    _DEFAULT_MODEL = "deepseek/deepseek-chat-v3-0324:free"

    def __init__(
        self,
        *,
        model: str = _DEFAULT_MODEL,
        tier: ModelTier = ModelTier.CHEAP,
        api_key: str | None = None,
    ) -> None:
        super().__init__(
            model=model,
            tier=tier,
            api_key=api_key,
            base_url=self._BASE_URL,
            name=f"openrouter:{model}",
        )


class CerebrasProvider(OpenAIProvider):
    """Cerebras — free tier, very fast inference."""

    _BASE_URL = "https://api.cerebras.ai/v1"
    _DEFAULT_MODEL = "llama-3.3-70b"

    def __init__(
        self,
        *,
        model: str = _DEFAULT_MODEL,
        tier: ModelTier = ModelTier.CHEAP,
        api_key: str | None = None,
    ) -> None:
        super().__init__(
            model=model,
            tier=tier,
            api_key=api_key,
            base_url=self._BASE_URL,
            name=f"cerebras:{model}",
        )


class MistralProvider(OpenAIProvider):
    """Mistral La Plateforme — has a free tier."""

    _BASE_URL = "https://api.mistral.ai/v1"
    _DEFAULT_MODEL = "mistral-small-latest"

    def __init__(
        self,
        *,
        model: str = _DEFAULT_MODEL,
        tier: ModelTier = ModelTier.CHEAP,
        api_key: str | None = None,
    ) -> None:
        super().__init__(
            model=model,
            tier=tier,
            api_key=api_key,
            base_url=self._BASE_URL,
            name=f"mistral:{model}",
        )
