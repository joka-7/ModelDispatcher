"""Per-tenant quota definitions and runtime context.

Multi-tenancy is modelled by attaching a :class:`TenantQuota` and resolved
credentials to a :class:`TenantContext`. The context is the unit the quota
manager, credential resolver, and onboarding resolver all key off, so a single
object carries a tenant's limits and identity through the whole pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..types import ModelTier, TenantId

__all__ = ["QuotaWindow", "TenantQuota", "TenantContext"]


@dataclass(frozen=True, slots=True)
class QuotaWindow:
    """A single rolling rate-limit window and its cap."""

    seconds: int
    max_tokens: int


@dataclass(frozen=True, slots=True)
class TenantQuota:
    """The full set of limits applied to one tenant.

    Attributes:
        requests_per_min: Cap on request count per minute.
        tokens_per_min: Cap on tokens per minute (short-burst protection).
        tokens_per_day: Cap on tokens per day (budget protection).
        budget_usd: Optional hard spend ceiling; ``None`` means untracked.
        soft_limit_ratio: Fraction of a window at which a ``SOFT_LIMIT`` warning
            is emitted before the hard ``DENY``.
    """

    requests_per_min: int
    tokens_per_min: int
    tokens_per_day: int
    budget_usd: float | None = None
    soft_limit_ratio: float = 0.9


@dataclass(frozen=True, slots=True)
class TenantContext:
    """Runtime identity + limits for the tenant a request belongs to.

    Attributes:
        tenant_id: The tenant this request is billed and quota-checked against.
        quota: The tenant's resolved limits.
        is_zero_setup: ``True`` when the tenant is riding the shared global app
            key / free tier rather than their own credential — the signal the
            onboarding resolver uses to decide Stage 1 vs Stage 2.
        max_tier: Highest tier this tenant is permitted to reach.
    """

    tenant_id: TenantId
    quota: TenantQuota
    is_zero_setup: bool = True
    max_tier: ModelTier = ModelTier.PREMIUM
    metadata: dict[str, str] = field(default_factory=dict)
