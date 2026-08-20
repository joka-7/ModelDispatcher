"""Persistence seam for tenant quota counters.

The :class:`QuotaStore` protocol is a narrow interface so the counting backend
can be swapped without touching the manager or any caller. This build ships only
:class:`InMemoryQuotaStore` (single-process, dict-backed); a distributed backend
(e.g. Redis with atomic INCR + TTL) can be dropped in later behind the same
protocol.
"""

from __future__ import annotations

import time
from typing import Protocol, TypeAlias, runtime_checkable

from ..types import TenantId

__all__ = ["WindowKey", "WINDOW_SECONDS", "QuotaStore", "InMemoryQuotaStore"]

WindowKey: TypeAlias = str
"""Identifies a (tenant, window) counter bucket, e.g. ``"tokens_per_min"``."""

# Duration of each named rolling window, in seconds. Fixed, tumbling windows are
# used (period = floor(now / duration)); a bucket auto-resets when the period
# rolls over, which is enough for fair short-horizon rate limiting.
WINDOW_SECONDS: dict[WindowKey, int] = {
    "requests_per_min": 60,
    "tokens_per_min": 60,
    "tokens_per_day": 86_400,
}


@runtime_checkable
class QuotaStore(Protocol):
    """Minimal counter store the quota manager depends on.

    Implementations must make :meth:`incr` atomic with respect to concurrent
    callers within their consistency domain (a process for the in-memory store,
    a cluster for a distributed one).
    """

    def read(self, tenant: TenantId, window: WindowKey) -> int:
        """Return the current token count for ``(tenant, window)`` this period."""
        ...

    def incr(self, tenant: TenantId, window: WindowKey, tokens: int) -> int:
        """Atomically add ``tokens`` and return the new running total."""
        ...

    def reset_expired(self) -> None:
        """Drop counters whose rolling window has elapsed."""
        ...


class InMemoryQuotaStore:
    """Single-process, dict-backed :class:`QuotaStore` implementation.

    Suitable for a single gateway worker or tests. Not safe across processes:
    each worker keeps its own counters, so horizontal scaling requires swapping
    in a shared-state backend behind the :class:`QuotaStore` protocol.
    """

    def __init__(self) -> None:
        # Keyed by (tenant, window) -> (count, period_index).
        self._counts: dict[tuple[TenantId, WindowKey], tuple[int, int]] = {}

    @staticmethod
    def _period(window: WindowKey) -> int:
        """Return the current tumbling-window index for ``window``."""
        duration = WINDOW_SECONDS[window]
        return int(time.monotonic() // duration)

    def read(self, tenant: TenantId, window: WindowKey) -> int:
        """See :meth:`QuotaStore.read`."""
        entry = self._counts.get((tenant, window))
        if entry is None or entry[1] != self._period(window):
            return 0
        return entry[0]

    def incr(self, tenant: TenantId, window: WindowKey, tokens: int) -> int:
        """See :meth:`QuotaStore.incr`."""
        period = self._period(window)
        entry = self._counts.get((tenant, window))
        current = entry[0] if entry is not None and entry[1] == period else 0
        updated = current + tokens
        self._counts[(tenant, window)] = (updated, period)
        return updated

    def reset_expired(self) -> None:
        """See :meth:`QuotaStore.reset_expired`."""
        stale = [
            key
            for key, (_, period) in self._counts.items()
            if period != self._period(key[1])
        ]
        for key in stale:
            del self._counts[key]
