"""Gateway assembly for the Vercel function.

Keeps the collaborator wiring — provider registry, settings, and the shared quota
store — in one place so :mod:`api.gateway` stays a thin adapter. The shipped
wiring uses keyless :class:`MockProvider` strategies so the template runs end to
end with zero secrets; swapping in real providers is a one-line change per tier
(see :func:`_register_providers`).

The quota store is module-scoped so usage accumulates across warm invocations of
the same serverless instance — the mechanism that lets a tenant actually reach the
Stage-2 key-wizard handoff.
"""

from __future__ import annotations

from model_dispatcher import (
    GatewaySettings,
    ModelGateway,
    ModelTier,
    ProviderRegistry,
    QuotaDefaults,
    TenantContext,
    TenantId,
    TenantQuota,
)
from model_dispatcher.providers import MockProvider
from model_dispatcher.quota.store import InMemoryQuotaStore, QuotaStore

# Deliberately small per-tenant budget so the onboarding handoff is reachable
# within a handful of requests. Tune per real product tiers.
_DEFAULT_QUOTA = TenantQuota(
    requests_per_min=30,
    tokens_per_min=4_000,
    tokens_per_day=40_000,
)
_SETTINGS = GatewaySettings(quota_defaults=QuotaDefaults())

# Process-wide, so repeated calls accumulate toward the limit.
_STORE: QuotaStore = InMemoryQuotaStore()


def _register_providers(registry: ProviderRegistry) -> None:
    """Register the model strategies, cheapest tier first.

    Replace each :class:`MockProvider` with a real adapter to go live, e.g.::

        from model_dispatcher.providers import OpenAIProvider, AnthropicProvider
        registry.register(OpenAIProvider("gpt-4o-mini", tier=ModelTier.STANDARD))
        registry.register(AnthropicProvider("claude-haiku-4-5", tier=ModelTier.FREE))

    The rest of the pipeline (routing, fallback, quota) is unchanged.
    """
    registry.register(
        MockProvider("mock:free", tier=ModelTier.FREE, reply="[free tier] Done.")
    )
    registry.register(
        MockProvider(
            "mock:standard", tier=ModelTier.STANDARD, reply="[standard tier] Done."
        )
    )
    registry.register(
        MockProvider(
            "mock:premium",
            tier=ModelTier.PREMIUM,
            reply="[premium tier] Reasoned answer.",
        )
    )


def build_gateway() -> ModelGateway:
    """Assemble a :class:`ModelGateway` over the shared quota store."""
    registry = ProviderRegistry()
    _register_providers(registry)
    return ModelGateway.create(registry, settings=_SETTINGS, quota_store=_STORE)


def build_tenant(tenant_id: str) -> TenantContext:
    """Build the per-request tenant context.

    Args:
        tenant_id: Stable identifier for the calling tenant (from the request; in
            a fuller build, derived from a verified Firebase Auth ID token).

    Returns:
        A zero-setup :class:`TenantContext` carrying the default quota, so a
        brand-new tenant starts on the shared free capacity (onboarding Stage 1).
    """
    return TenantContext(
        tenant_id=TenantId(tenant_id),
        quota=_DEFAULT_QUOTA,
        is_zero_setup=True,
    )
