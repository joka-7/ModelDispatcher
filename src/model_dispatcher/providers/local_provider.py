"""Local / free provider strategy (skeleton).

Backs the zero-setup onboarding stage: a locally hosted or free-tier model that
requires no user credential. Registered at :data:`ModelTier.FREE`, it is the
first candidate the router offers for trivial work and the safety net the
fallback chain lands on before triggering the key wizard.
"""

from __future__ import annotations

from typing_extensions import override

from ..types import (
    CompletionRequest,
    CompletionResponse,
    ErrorClass,
    ModelTier,
    ProviderCapability,
)
from .base import ModelProvider

__all__ = ["LocalProvider"]


class LocalProvider(ModelProvider):
    """Adapter for a local or free-tier model requiring no user credential."""

    def __init__(
        self,
        *,
        model: str = "local-default",
        endpoint: str | None = None,
    ) -> None:
        self.name = f"local:{model}"
        self.tier = ModelTier.FREE
        self.capabilities = ProviderCapability.TOOLS
        self._model = model
        self._endpoint = endpoint

    @override
    def complete(
        self, request: CompletionRequest, *, api_key: str | None = None
    ) -> CompletionResponse:
        raise NotImplementedError

    @override
    async def acomplete(
        self, request: CompletionRequest, *, api_key: str | None = None
    ) -> CompletionResponse:
        raise NotImplementedError

    @override
    def estimate_tokens(self, request: CompletionRequest) -> int:
        raise NotImplementedError

    @override
    def classify_error(self, exc: Exception) -> ErrorClass:
        """Map local runtime/connection failures onto normalised classes."""
        raise NotImplementedError
