"""Persistence seam for tenant quota counters.

The :class:`QuotaStore` protocol is a narrow interface so the counting backend
can be swapped without touching the manager or any caller. This build ships only
:class:`InMemoryQuotaStore` (single-process, dict-backed); a distributed backend
(e.g. Redis with atomic INCR + TTL) can be dropped in later behind the same
protocol.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..types import TenantId

__all__ = ["WindowKey", "QuotaStore", "InMemoryQuotaStore"]

type WindowKey = str
"""Identifies a (tenant, window) counter bucket, e.g. ``"tokens_per_min"``."""


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
        # Keyed by (tenant, window) -> (count, window_start_monotonic).
        self._counts: dict[tuple[TenantId, WindowKey], tuple[int, float]] = {}

    def read(self, tenant: TenantId, window: WindowKey) -> int:
        """See :meth:`QuotaStore.read`."""
        raise NotImplementedError

    def incr(self, tenant: TenantId, window: WindowKey, tokens: int) -> int:
        """See :meth:`QuotaStore.incr`."""
        raise NotImplementedError

    def reset_expired(self) -> None:
        """See :meth:`QuotaStore.reset_expired`."""
        raise NotImplementedError
