"""Vendor-neutral metrics hooks.

Defines a minimal sink protocol so the gateway can emit counters and timings
(dispatch latency, fallback depth, tokens per tenant, quota denials) without
binding to a specific metrics backend. Applications supply an adapter.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["MetricsSink", "NullMetricsSink"]


@runtime_checkable
class MetricsSink(Protocol):
    """Minimal metrics interface the gateway emits through."""

    def increment(self, name: str, value: int = 1, **tags: str) -> None:
        """Add ``value`` to the counter ``name`` under the given ``tags``."""
        ...

    def observe(self, name: str, value: float, **tags: str) -> None:
        """Record a distribution/timing sample for ``name``."""
        ...


class NullMetricsSink:
    """No-op :class:`MetricsSink` used when the app supplies no backend."""

    def increment(self, name: str, value: int = 1, **tags: str) -> None:
        """Discard the counter increment."""

    def observe(self, name: str, value: float, **tags: str) -> None:
        """Discard the observation."""
