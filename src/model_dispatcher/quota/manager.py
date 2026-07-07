"""Token-aware, multi-tenant quota manager.

The manager enforces limits in two phases around each model call:

* **reserve** — before the call, estimate the cost and decide ALLOW / SOFT_LIMIT
  / DENY against the tenant's windows.
* **commit** — after the call, reconcile the reservation against the *actual*
  usage the provider reported, correcting the estimate so counters stay accurate.

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
            For each of the tenant's windows (per-minute, per-day, budget),
            read the current counter and test ``current + estimate`` against the
            cap. The strictest verdict wins: any hard breach yields ``DENY``;
            otherwise crossing ``soft_limit_ratio`` yields ``SOFT_LIMIT``; else
            ``ALLOW``. On a non-deny verdict the estimate is written to the store
            so concurrent requests see the reservation immediately.
        """
        raise NotImplementedError

    def commit(self, tenant: TenantContext, actual: Usage) -> None:
        """Reconcile a prior reservation against the provider-reported usage.

        Adjusts the tenant's counters by the delta between the reserved estimate
        and ``actual.total_tokens`` so long-running accuracy does not drift.
        """
        raise NotImplementedError
