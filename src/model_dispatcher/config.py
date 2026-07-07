"""Declarative configuration for a :class:`ModelGateway` instance.

Configuration is intentionally plain data: a :class:`GatewaySettings` bundle is
constructed once at application start and injected into the gateway. Routing
behaviour, quota defaults, and security posture are all expressed here so
operational tuning never requires touching code.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .types import ModelTier, TaskComplexity

__all__ = [
    "RoutingPolicy",
    "SecuritySettings",
    "QuotaDefaults",
    "GatewaySettings",
]


@dataclass(frozen=True, slots=True)
class RoutingPolicy:
    """Maps triage verdicts onto the minimum acceptable model tier.

    Attributes:
        complexity_floor: For each :class:`TaskComplexity`, the lowest tier a
            candidate may occupy. Defaults escalate monotonically so trivial work
            stays free while complex reasoning reserves premium models.
        allow_escalation: When ``True``, the router appends higher tiers after the
            floor so fallback can climb; when ``False`` it stays within one tier.
        max_candidates: Cap on how many providers seed the fallback chain.
    """

    complexity_floor: dict[TaskComplexity, ModelTier] = field(
        default_factory=lambda: {
            TaskComplexity.TRIVIAL: ModelTier.FREE,
            TaskComplexity.SIMPLE: ModelTier.CHEAP,
            TaskComplexity.MODERATE: ModelTier.STANDARD,
            TaskComplexity.COMPLEX: ModelTier.PREMIUM,
        }
    )
    allow_escalation: bool = True
    max_candidates: int = 4


@dataclass(frozen=True, slots=True)
class SecuritySettings:
    """Perimeter posture applied to every inbound request.

    Attributes:
        max_payload_bytes: Reject requests whose serialised body exceeds this.
        allowed_providers: Optional allowlist of provider names permitted as
            egress targets; empty means "all registered providers".
        require_tenant_auth: When ``True``, requests without a resolvable tenant
            credential are rejected at the perimeter.
    """

    max_payload_bytes: int = 1_000_000
    allowed_providers: frozenset[str] = frozenset()
    require_tenant_auth: bool = True


@dataclass(frozen=True, slots=True)
class QuotaDefaults:
    """Fallback per-tenant limits applied when a tenant has no explicit quota.

    These also back the Stage-1 zero-setup experience: the rate-limited global
    app key is modelled as a tenant carrying these defaults.
    """

    requests_per_min: int = 20
    tokens_per_min: int = 40_000
    tokens_per_day: int = 1_000_000
    budget_usd: float | None = None
    soft_limit_ratio: float = 0.9


@dataclass(frozen=True, slots=True)
class GatewaySettings:
    """Top-level configuration bundle injected into :class:`ModelGateway`.

    Attributes:
        routing: Complexity-to-tier policy driving candidate selection.
        security: Perimeter validation posture.
        quota_defaults: Default limits for tenants lacking an explicit quota.
        global_app_tenant: Identity of the shared, rate-limited key used for the
            zero-setup onboarding stage.
        max_iterations: Hard ceiling on agent-loop turns per dispatch.
        retry_max_attempts: Bounded retries for transient provider failures.
    """

    routing: RoutingPolicy = field(default_factory=RoutingPolicy)
    security: SecuritySettings = field(default_factory=SecuritySettings)
    quota_defaults: QuotaDefaults = field(default_factory=QuotaDefaults)
    global_app_tenant: str = "__global_app__"
    max_iterations: int = 8
    retry_max_attempts: int = 3
