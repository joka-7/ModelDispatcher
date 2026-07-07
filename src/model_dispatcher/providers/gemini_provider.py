"""Google Gemini provider strategy (skeleton).

Adapter for Google Gemini models. The ``google-generativeai`` SDK is an optional
extra imported lazily inside method bodies.
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

__all__ = ["GeminiProvider"]


class GeminiProvider(ModelProvider):
    """Adapter for Google Gemini models."""

    def __init__(
        self,
        *,
        model: str,
        tier: ModelTier = ModelTier.CHEAP,
        api_key: str | None = None,
    ) -> None:
        self.name = f"gemini:{model}"
        self.tier = tier
        self.capabilities = (
            ProviderCapability.TOOLS
            | ProviderCapability.STREAMING
            | ProviderCapability.VISION
            | ProviderCapability.JSON_MODE
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
        """Map ``google.api_core`` resource-exhausted errors onto normalised classes."""
        raise NotImplementedError
