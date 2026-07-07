"""Chain-of-Responsibility handlers for a single model invocation.

Each handler owns one concern (perimeter, credentials, quota, invocation) and
returns a :class:`HandlerOutcome` telling the executor how to proceed. The chain
is what makes fallback transparent: a rate-limited or exhausted provider is
intercepted here and the executor swaps in the next candidate without the caller
ever seeing the failure.

Transient retries (bounded exponential backoff) and rate-limit failover are both
folded into :class:`ModelInvocationHandler` because they wrap the same network
call; :func:`~model_dispatcher.fallback.conditions` decides which class of
failure triggers which behaviour.
"""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto

from ..exceptions import (
    AuthenticationError,
    ModelDispatcherError,
    QuotaExceededError,
)
from ..onboarding.flow import OnboardingResolver
from ..providers.base import ModelProvider
from ..quota.manager import QuotaDecision, QuotaManager, QuotaOutcome
from ..quota.tenant import TenantContext
from ..security.credentials import Credential, CredentialResolver
from ..security.perimeter import PerimeterValidator
from ..types import (
    CompletionRequest,
    CompletionResponse,
    ErrorClass,
    ModelTier,
)
from .conditions import is_fallback_worthy, is_retryable

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
        tenant: The tenant the request is billed and quota-checked against.
        candidates: Ordered providers from the router; index 0 is "current".
            Consumed from the front as the chain falls back.
        attempts: Append-only record of every provider tried this turn.
        credential: Credential resolved for the current candidate.
        reservation: Quota decision for the current candidate (drives commit).
        response: Populated by the invocation handler on success.
        error: Set when a handler decides the chain must ``STOP``.
        warnings: Non-fatal notes (e.g. soft-limit approaching) for the caller.
    """

    request: CompletionRequest
    tenant: TenantContext
    candidates: list[ModelProvider]
    attempts: list[AttemptRecord] = field(default_factory=list)
    credential: Credential | None = None
    reservation: QuotaDecision | None = None
    response: CompletionResponse | None = None
    error: Exception | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def current(self) -> ModelProvider | None:
        """Return the candidate currently being attempted, if any remain."""
        return self.candidates[0] if self.candidates else None

    def reset_candidate_state(self) -> None:
        """Clear per-candidate scratch state before falling back to the next."""
        self.credential = None
        self.reservation = None


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
    """First link: reject requests that fail security-perimeter validation."""

    def __init__(self, validator: PerimeterValidator) -> None:
        super().__init__()
        self._validator = validator

    def handle(self, context: InvocationContext) -> HandlerOutcome:
        """Validate the request at the trust edge (raises on violation)."""
        self._validator.validate(context.request, context.tenant)
        return HandlerOutcome.CONTINUE

    async def ahandle(self, context: InvocationContext) -> HandlerOutcome:
        """Async mirror of :meth:`handle` (validation is CPU-bound)."""
        return self.handle(context)


class CredentialHandler(FallbackHandler):
    """Resolve the credential for the current candidate via the precedence chain.

    Missing user/tenant keys fall back to the rate-limited global app key — the
    mechanical basis of the zero-setup onboarding stage.
    """

    def __init__(self, resolver: CredentialResolver) -> None:
        super().__init__()
        self._resolver = resolver

    def handle(self, context: InvocationContext) -> HandlerOutcome:
        """Attach the highest-precedence credential to the context."""
        provider = context.current
        if provider is None:
            return HandlerOutcome.FALLBACK
        context.credential = self._resolver.resolve(context.tenant, provider)
        return HandlerOutcome.CONTINUE

    async def ahandle(self, context: InvocationContext) -> HandlerOutcome:
        """Async mirror of :meth:`handle`."""
        return self.handle(context)


class QuotaHandler(FallbackHandler):
    """Pre-flight token-quota reservation for the current tenant/candidate.

    On a hard breach this raises :class:`QuotaExceededError` (Stage-2 handoff)
    unless the tenant is zero-setup and a cheaper free candidate remains, in
    which case it returns ``FALLBACK`` to stay within the zero-setup stage.
    """

    def __init__(self, manager: QuotaManager, onboarding: OnboardingResolver) -> None:
        super().__init__()
        self._manager = manager
        self._onboarding = onboarding

    def handle(self, context: InvocationContext) -> HandlerOutcome:
        """Reserve quota for the current candidate or escalate on breach."""
        provider = context.current
        if provider is None:
            return HandlerOutcome.FALLBACK

        estimate = provider.estimate_tokens(context.request)
        decision = self._manager.reserve(context.tenant, estimate, provider)

        if decision.outcome is QuotaOutcome.DENY:
            return self._on_deny(context, provider, decision)

        if decision.outcome is QuotaOutcome.SOFT_LIMIT:
            context.warnings.append(
                f"quota soft limit approaching for {decision.breached_window}"
            )
        context.reservation = decision
        return HandlerOutcome.CONTINUE

    async def ahandle(self, context: InvocationContext) -> HandlerOutcome:
        """Async mirror of :meth:`handle` (reservation is CPU-bound)."""
        return self.handle(context)

    def _on_deny(
        self,
        context: InvocationContext,
        provider: ModelProvider,
        decision: QuotaDecision,
    ) -> HandlerOutcome:
        """Decide between staying zero-setup and raising the Stage-2 handoff."""
        cheaper_free_remaining = any(
            candidate.tier is ModelTier.FREE for candidate in context.candidates[1:]
        )
        if context.tenant.is_zero_setup and cheaper_free_remaining:
            return HandlerOutcome.FALLBACK

        rate_window = decision.breached_window in (
            "requests_per_min",
            "tokens_per_min",
        )
        handoff = self._onboarding.escalate(
            context.tenant, provider.name, rate_window=rate_window
        )
        raise QuotaExceededError(handoff)


class ModelInvocationHandler(FallbackHandler):
    """Call the current candidate, with transient retry and rate-limit failover.

    Algorithm:
        Attempt ``provider.complete``. On success, record the attempt, commit the
        quota reservation against actual usage, and return ``SUCCESS``. On a
        vendor error, normalise it via ``provider.classify_error`` and:

        * transient → retry the same provider up to ``max_attempts`` with
          exponential backoff, then fall back;
        * rate-limit / quota → ``FALLBACK`` to the next candidate immediately;
        * terminal (auth/invalid/content) → ``STOP`` with a mapped exception.
    """

    def __init__(
        self,
        manager: QuotaManager,
        *,
        max_attempts: int = 3,
        backoff_base: float = 0.05,
        backoff_cap: float = 2.0,
    ) -> None:
        super().__init__()
        self._manager = manager
        self._max_attempts = max_attempts
        self._backoff_base = backoff_base
        self._backoff_cap = backoff_cap

    def handle(self, context: InvocationContext) -> HandlerOutcome:
        """Invoke the current candidate synchronously."""
        provider = context.current
        if provider is None:
            return HandlerOutcome.FALLBACK

        for attempt in range(1, self._max_attempts + 1):
            try:
                response = provider.complete(context.request)
            except ModelDispatcherError:
                raise
            except Exception as exc:  # noqa: BLE001 - normalised via classify_error
                outcome = self._on_error(context, provider, exc, attempt)
                if outcome is None:
                    time.sleep(self._backoff_delay(attempt))
                    continue
                return outcome
            return self._on_success(context, provider, response)

        return HandlerOutcome.FALLBACK  # retries exhausted; try the next provider

    async def ahandle(self, context: InvocationContext) -> HandlerOutcome:
        """Invoke the current candidate asynchronously."""
        provider = context.current
        if provider is None:
            return HandlerOutcome.FALLBACK

        for attempt in range(1, self._max_attempts + 1):
            try:
                response = await provider.acomplete(context.request)
            except ModelDispatcherError:
                raise
            except Exception as exc:  # noqa: BLE001 - normalised via classify_error
                outcome = self._on_error(context, provider, exc, attempt)
                if outcome is None:
                    await asyncio.sleep(self._backoff_delay(attempt))
                    continue
                return outcome
            return self._on_success(context, provider, response)

        return HandlerOutcome.FALLBACK

    def _on_success(
        self,
        context: InvocationContext,
        provider: ModelProvider,
        response: CompletionResponse,
    ) -> HandlerOutcome:
        """Record success and reconcile the quota reservation."""
        context.attempts.append(AttemptRecord(provider.name))
        context.response = response
        if context.reservation is not None:
            self._manager.commit(context.tenant, context.reservation, response.usage)
        return HandlerOutcome.SUCCESS

    def _on_error(
        self,
        context: InvocationContext,
        provider: ModelProvider,
        exc: Exception,
        attempt: int,
    ) -> HandlerOutcome | None:
        """Classify an error and decide the next step.

        Returns ``None`` to signal "retry the same provider after backoff", or a
        concrete :class:`HandlerOutcome` (FALLBACK / STOP) to act on now.
        """
        error_class = provider.classify_error(exc)
        context.attempts.append(AttemptRecord(provider.name, error_class, str(exc)))

        if is_retryable(error_class) and attempt < self._max_attempts:
            return None
        if is_fallback_worthy(error_class) or is_retryable(error_class):
            return HandlerOutcome.FALLBACK

        context.error = self._terminal_error(provider.name, error_class, exc)
        return HandlerOutcome.STOP

    def _backoff_delay(self, attempt: int) -> float:
        """Return the exponential-backoff delay (seconds) for ``attempt``."""
        return min(self._backoff_base * (2.0 ** (attempt - 1)), self._backoff_cap)

    @staticmethod
    def _terminal_error(
        provider_name: str, error_class: ErrorClass, exc: Exception
    ) -> ModelDispatcherError:
        """Map a terminal provider failure onto a library exception."""
        if error_class is ErrorClass.AUTH:
            return AuthenticationError(f"{provider_name}: {exc}")
        error = ModelDispatcherError(
            f"{provider_name} failed ({error_class.value}): {exc}"
        )
        error.http_status = 502
        error.error_code = f"provider_{error_class.value}"
        return error


class RateLimitHandler(FallbackHandler):
    """Optional standalone rate-limit failover link.

    Rate-limit failover is handled inside :class:`ModelInvocationHandler` in the
    default chain; this class remains available for compositions that want the
    concern isolated. It simply reports whether the current candidate's last
    recorded error was fallback-worthy.
    """

    def handle(self, context: InvocationContext) -> HandlerOutcome:
        """Return ``FALLBACK`` when the last attempt was rate-limited."""
        if context.attempts and context.attempts[-1].error_class is not None:
            if is_fallback_worthy(context.attempts[-1].error_class):
                return HandlerOutcome.FALLBACK
        return HandlerOutcome.CONTINUE

    async def ahandle(self, context: InvocationContext) -> HandlerOutcome:
        """Async mirror of :meth:`handle`."""
        return self.handle(context)


class RetryHandler(FallbackHandler):
    """Optional standalone transient-retry configuration holder.

    Bounded retry is handled inside :class:`ModelInvocationHandler` in the
    default chain; this class carries the retry budget for compositions that
    prefer to configure it separately.
    """

    def __init__(self, max_attempts: int) -> None:
        super().__init__()
        self._max_attempts = max_attempts

    @property
    def max_attempts(self) -> int:
        """Return the configured retry budget."""
        return self._max_attempts

    def handle(self, context: InvocationContext) -> HandlerOutcome:
        """No-op pass-through in the default composition."""
        return HandlerOutcome.CONTINUE

    async def ahandle(self, context: InvocationContext) -> HandlerOutcome:
        """Async mirror of :meth:`handle`."""
        return HandlerOutcome.CONTINUE
