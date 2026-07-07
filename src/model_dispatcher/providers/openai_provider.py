"""OpenAI provider strategy (skeleton).

Concrete adapter that will translate :class:`CompletionRequest` objects into
OpenAI Chat Completions calls and normalise the vendor's rate-limit/quota
exceptions into :class:`ErrorClass` values. The ``openai`` SDK is an optional
extra; it is imported lazily inside method bodies (not at module import) so the
core library stays dependency-free.
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

__all__ = ["OpenAIProvider"]


class OpenAIProvider(ModelProvider):
    """Adapter for OpenAI chat models."""

    def __init__(
        self,
        *,
        model: str,
        tier: ModelTier = ModelTier.STANDARD,
        api_key: str | None = None,
    ) -> None:
        self.name = f"openai:{model}"
        self.tier = tier
        self.capabilities = (
            ProviderCapability.TOOLS
            | ProviderCapability.STREAMING
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
        """Map OpenAI SDK rate-limit/API errors onto normalised classes."""
        raise NotImplementedError
