"""Chain-of-Responsibility handlers for a single model invocation.

Each handler owns one concern (perimeter, credentials, quota, invocation, rate
limits, retries) and either handles the :class:`InvocationContext` or passes it
along. The chain is what makes fallback transparent: a rate-limited provider is
intercepted here and swapped for the next candidate without the caller ever
seeing the failure.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto

from ..providers.base import ModelProvider
from ..types import CompletionRequest, CompletionResponse, ErrorClass

__all__ = [
    "HandlerOutcome",
    "AttemptRecord",
    "InvocationContext",
    "FallbackHandler",
    "PerimeterHandler",
    "CredentialHandler",
    "QuotaHandler",
    "ModelInvocationHandler",
    "RateLimitHandler",
    "RetryHandler",
]


class HandlerOutcome(Enum):
    """The verdict a handler returns to the chain executor.

    Members:
        CONTINUE: This handler is satisfied; hand the context to the next link.
        SUCCESS: A response was produced; unwind and return it.
        FALLBACK: Drop the current candidate and restart the chain with the next.
        STOP: Abort the whole chain; the context carries the error to raise.
    """

    CONTINUE = auto()
    SUCCESS = auto()
    FALLBACK = auto()
    STOP = auto()


@dataclass(slots=True)
class AttemptRecord:
    """Audit trail entry for one provider attempt within a dispatch."""

    provider_name: str
    error_class: ErrorClass | None = None
    detail: str | None = None


@dataclass(slots=True)
class InvocationContext:
    """Mutable state threaded through the fallback chain for one model turn.

    Attributes:
        request: The completion request for this turn.
        candidates: Ordered providers from the router; index 0 is "current".
            Consumed from the front as the chain falls back.
        attempts: Append-only record of every provider tried this turn.
        response: Populated by the invocation handler on success.
        error: Set when a handler decides the chain must ``STOP``.
    """

    request: CompletionRequest
    candidates: list[ModelProvider]
    attempts: list[AttemptRecord] = field(default_factory=list)
    response: CompletionResponse | None = None
    error: Exception | None = None

    @property
    def current(self) -> ModelProvider | None:
        """Return the candidate currently being attempted, if any remain."""
        raise NotImplementedError


class FallbackHandler(ABC):
    """Base link in the chain of responsibility.

    Subclasses implement :meth:`handle`/:meth:`ahandle` and return a
    :class:`HandlerOutcome`; the executor (see :mod:`.chain`) interprets that
    outcome and decides whether to advance, restart, succeed, or stop.
    """

    def __init__(self) -> None:
        self._next: FallbackHandler | None = None

    def set_next(self, handler: FallbackHandler) -> FallbackHandler:
        """Link ``handler`` after this one and return it for fluent chaining."""
        self._next = handler
        return handler

    @abstractmethod
    def handle(self, context: InvocationContext) -> HandlerOutcome:
        """Process ``context`` synchronously and return an outcome."""
        ...

    @abstractmethod
    async def ahandle(self, context: InvocationContext) -> HandlerOutcome:
        """Process ``context`` asynchronously and return an outcome."""
        ...


class PerimeterHandler(FallbackHandler):
    """First link: reject requests that fail security-perimeter validation.

    Concrete behaviour (``handle``/``ahandle``) is supplied in the implementation
    phase; the class stays abstract until then.
    """


class CredentialHandler(FallbackHandler):
    """Resolve the credential for the current candidate via the precedence chain.

    Missing user/tenant keys fall back to the rate-limited global app key — the
    mechanical basis of the zero-setup onboarding stage.
    """


class QuotaHandler(FallbackHandler):
    """Pre-flight token-quota reservation for the current tenant/candidate.

    On a hard breach this raises :class:`QuotaExceededError` (Stage-2 handoff)
    unless a cheaper free candidate remains, in which case it returns
    ``FALLBACK`` to stay within the zero-setup stage.
    """


class ModelInvocationHandler(FallbackHandler):
    """Call the current candidate and store its response on the context."""


class RateLimitHandler(FallbackHandler):
    """Turn a provider rate limit / exhaustion into a ``FALLBACK`` to the next model."""


class RetryHandler(FallbackHandler):
    """Bounded exponential-backoff retry for transient failures on one candidate."""

    def __init__(self, max_attempts: int) -> None:
        super().__init__()
        self._max_attempts = max_attempts
