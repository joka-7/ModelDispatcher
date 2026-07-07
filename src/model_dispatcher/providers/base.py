"""The Strategy interface for model providers.

Every backend (OpenAI, Anthropic, Gemini, a local model) is a *strategy*: it
implements the same :class:`ModelProvider` contract, so the rest of the gateway
depends only on this abstraction and never on a vendor SDK. Swapping, adding, or
reordering providers is therefore a registration concern, not a code change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..types import (
    CompletionRequest,
    CompletionResponse,
    ErrorClass,
    ModelTier,
    ProviderCapability,
)

__all__ = ["ModelProvider"]


class ModelProvider(ABC):
    """Abstract strategy every concrete model backend must implement.

    Attributes:
        name: Stable, unique identifier used in registries, logs, and payloads.
        tier: Cost/capability tier used by routing and quota attribution.
        capabilities: Feature flags advertised to the router for filtering.
    """

    name: str
    tier: ModelTier
    capabilities: ProviderCapability

    @abstractmethod
    def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Produce a single completion synchronously.

        Implementations should translate the vendor response into a
        :class:`CompletionResponse` and let vendor exceptions propagate — the
        fallback chain relies on :meth:`classify_error` to interpret them.
        """
        ...

    @abstractmethod
    async def acomplete(self, request: CompletionRequest) -> CompletionResponse:
        """Async counterpart of :meth:`complete`."""
        ...

    @abstractmethod
    def estimate_tokens(self, request: CompletionRequest) -> int:
        """Return a pre-flight estimate of the request's prompt-token cost.

        Used by the quota subsystem to *reserve* capacity before the call. The
        estimate should err slightly high so reservations are conservative.
        """
        ...

    @abstractmethod
    def classify_error(self, exc: Exception) -> ErrorClass:
        """Map a vendor-specific exception onto a normalised :class:`ErrorClass`.

        This is the seam that lets the fallback chain treat "rate limited",
        "out of quota", and "transient network blip" uniformly across providers.
        """
        ...
