"""Token-aware, multi-tenant quota manager.

The manager enforces limits in two phases around each model call:

* **reserve** — before the call, estimate the cost and decide ALLOW / SOFT_LIMIT
  / DENY against the tenant's windows, pre-charging the estimate so concurrent
  in-flight requests see each other.
* **commit** — after the call, reconcile the reservation against the *actual*
  usage the provider reported, correcting the pre-charge so counters stay
  accurate.

This reserve/commit split is what makes quota enforcement token-aware rather than
merely request-counting.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ..providers.base import ModelProvider
from ..types import Usage
from .store import QuotaStore
from .tenant import TenantContext

__all__ = ["QuotaOutcome", "QuotaDecision", "QuotaManager"]


class QuotaOutcome(StrEnum):
    """Verdict of a :meth:`QuotaManager.reserve` check."""

    ALLOW = "allow"
    SOFT_LIMIT = "soft_limit"
    DENY = "deny"


@dataclass(frozen=True, slots=True)
class QuotaDecision:
    """Result of a reservation attempt.

    Attributes:
        outcome: ALLOW, SOFT_LIMIT (proceed but warn), or DENY (block).
        reserved_tokens: Tokens provisionally charged, reconciled at commit.
        breached_window: Name of the window that tripped a SOFT_LIMIT/DENY.
        provider_name: Provider the reservation was scoped to.
    """

    outcome: QuotaOutcome
    reserved_tokens: int
    breached_window: str | None = None
    provider_name: str | None = None


class QuotaManager:
    """Enforces per-tenant token budgets via a pluggable :class:`QuotaStore`."""

    def __init__(self, store: QuotaStore) -> None:
        self._store = store

    def reserve(
        self,
        tenant: TenantContext,
        estimated_tokens: int,
        provider: ModelProvider,
    ) -> QuotaDecision:
        """Provisionally charge ``estimated_tokens`` and return the verdict.

        Algorithm:
            For each of the tenant's windows (requests/min, tokens/min,
            tokens/day) read the current counter and test the prospective total
            against the cap. The strictest verdict wins: any hard breach yields
            ``DENY``; otherwise crossing ``soft_limit_ratio`` of any window yields
            ``SOFT_LIMIT``; else ``ALLOW``. On a non-deny verdict the request and
            token counters are incremented so concurrent requests see the
            reservation immediately.
        """
        quota = tenant.quota
        tid = tenant.tenant_id

        checks: list[tuple[str, int, int]] = [
            (
                "requests_per_min",
                self._store.read(tid, "requests_per_min") + 1,
                quota.requests_per_min,
            ),
            (
                "tokens_per_min",
                self._store.read(tid, "tokens_per_min") + estimated_tokens,
                quota.tokens_per_min,
            ),
            (
                "tokens_per_day",
                self._store.read(tid, "tokens_per_day") + estimated_tokens,
                quota.tokens_per_day,
            ),
        ]

        outcome = QuotaOutcome.ALLOW
        breached: str | None = None
        for window, prospective, cap in checks:
            if prospective > cap:
                return QuotaDecision(
                    outcome=QuotaOutcome.DENY,
                    reserved_tokens=0,
                    breached_window=window,
                    provider_name=provider.name,
                )
            if prospective > cap * quota.soft_limit_ratio:
                outcome = QuotaOutcome.SOFT_LIMIT
                breached = window

        self._store.incr(tid, "requests_per_min", 1)
        self._store.incr(tid, "tokens_per_min", estimated_tokens)
        self._store.incr(tid, "tokens_per_day", estimated_tokens)

        return QuotaDecision(
            outcome=outcome,
            reserved_tokens=estimated_tokens,
            breached_window=breached,
            provider_name=provider.name,
        )

    def commit(
        self,
        tenant: TenantContext,
        decision: QuotaDecision,
        actual: Usage,
    ) -> None:
        """Reconcile a prior reservation against provider-reported usage.

        Adjusts the tenant's token counters by the delta between the reserved
        estimate and ``actual.total_tokens`` so long-running accuracy does not
        drift. A negative delta (the estimate over-counted) refunds the tenant.
        """
        delta = actual.total_tokens - decision.reserved_tokens
        if delta == 0:
            return
        self._store.incr(tenant.tenant_id, "tokens_per_min", delta)
        self._store.incr(tenant.tenant_id, "tokens_per_day", delta)
