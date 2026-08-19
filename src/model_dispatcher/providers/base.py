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
from .retry_hints import extract_retry_after_seconds

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
    def complete(
        self, request: CompletionRequest, *, api_key: str | None = None
    ) -> CompletionResponse:
        """Produce a single completion synchronously.

        Args:
            request: The completion request to serve.
            api_key: Per-call credential override. When set, implementations
                must use this instead of whatever key the instance was
                constructed with — this is how
                :class:`~model_dispatcher.fallback.handlers.ModelInvocationHandler`
                applies a resolved tenant/user credential (or rotates through
                several) without needing a separate provider instance per key.
                ``None`` keeps the instance's own configured key.

        Implementations should translate the vendor response into a
        :class:`CompletionResponse` and let vendor exceptions propagate — the
        fallback chain relies on :meth:`classify_error` to interpret them.
        """
        ...

    @abstractmethod
    async def acomplete(
        self, request: CompletionRequest, *, api_key: str | None = None
    ) -> CompletionResponse:
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

    def retry_after_seconds(self, exc: Exception) -> float | None:
        """Best-effort "how long until this provider will accept another call".

        Only ever consulted for a :class:`ErrorClass.RATE_LIMIT` failure with
        no fallback candidate left (see
        :class:`~model_dispatcher.fallback.handlers.ModelInvocationHandler`) —
        the one situation where waiting is strictly better than failing
        immediately. The default implementation is generic and provider-
        agnostic (works for every vendor without per-provider code): it tries
        the exception's HTTP ``Retry-After`` response header first, then
        falls back to parsing a hint out of the exception's own message text
        (covers Anthropic/Groq-style "try again in 48m55s" messages that
        aren't in a header at all). Returns ``None`` when no hint can be
        found — callers fall back to plain exponential backoff in that case.
        Override this only if a provider needs something more precise than
        the generic extraction.
        """
        return extract_retry_after_seconds(exc)
