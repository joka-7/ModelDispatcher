"""Anthropic provider strategy (skeleton).

Adapter for Anthropic Claude models. Like the other adapters, the ``anthropic``
SDK is an optional extra imported lazily inside method bodies so importing the
core package never requires the vendor dependency.
"""

from __future__ import annotations

from typing import override

from ..types import (
    CompletionRequest,
    CompletionResponse,
    ErrorClass,
    ModelTier,
    ProviderCapability,
)
from .base import ModelProvider

__all__ = ["AnthropicProvider"]


class AnthropicProvider(ModelProvider):
    """Adapter for Anthropic Claude models."""

    def __init__(
        self,
        *,
        model: str,
        tier: ModelTier = ModelTier.PREMIUM,
        api_key: str | None = None,
    ) -> None:
        self.name = f"anthropic:{model}"
        self.tier = tier
        self.capabilities = (
            ProviderCapability.TOOLS
            | ProviderCapability.STREAMING
            | ProviderCapability.VISION
        )
        self._model = model
        self._api_key = api_key

    @override
    def complete(self, request: CompletionRequest) -> CompletionResponse:
        raise NotImplementedError

    @override
    async def acomplete(self, request: CompletionRequest) -> CompletionResponse:
        raise NotImplementedError

    @override
    def estimate_tokens(self, request: CompletionRequest) -> int:
        raise NotImplementedError

    @override
    def classify_error(self, exc: Exception) -> ErrorClass:
        """Map Anthropic SDK rate-limit/status errors onto normalised classes."""
        raise NotImplementedError
