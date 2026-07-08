"""Gateway assembly for the Vercel function.

Keeps the collaborator wiring — provider registry, settings, and the shared quota
store — in one place so :mod:`api.gateway` stays a thin adapter.

:func:`_register_providers` registers a *real* adapter (:class:`OpenAIProvider`,
:class:`AnthropicProvider`, :class:`GeminiProvider`) for every provider whose API
key env var is set, and falls back to a keyless :class:`MockProvider` for any tier
left unconfigured — so a fresh checkout with zero secrets still runs end to end
(all mocks), and setting one or more keys upgrades exactly those tiers to live
models with no other code change.

The quota store is module-scoped so usage accumulates across warm invocations of
the same serverless instance — the mechanism that lets a tenant actually reach the
Stage-2 key-wizard handoff.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass

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
from model_dispatcher.providers import (
    AnthropicProvider,
    GeminiProvider,
    MockProvider,
    OpenAIProvider,
)
from model_dispatcher.providers.base import ModelProvider
from model_dispatcher.quota.store import InMemoryQuotaStore, QuotaStore

#: Builds a live adapter from ``(model, tier, api_key)``. A plain callable (rather
#: than a bare class reference) keeps the call site's signature explicit and
#: identical across vendors, so mypy checks it without needing a per-call ignore.
ProviderFactory = Callable[[str, ModelTier, str], ModelProvider]

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


@dataclass(frozen=True, slots=True)
class _ProviderSlot:
    """One tier's live-vs-mock configuration.

    Attributes:
        tier: The cost tier this slot fills in the routing ladder.
        api_key_env: Env var holding the vendor API key; unset means "use mock".
        model_env: Env var overriding the default model id for this tier.
        default_model: Model id used when ``model_env`` is unset.
        build: Constructs the live adapter given ``(model, tier, api_key)``.
        mock_reply: Canned reply the keyless fallback returns.
    """

    tier: ModelTier
    api_key_env: str
    model_env: str
    default_model: str
    build: ProviderFactory
    mock_reply: str


# Cheapest tier first: routing/fallback consumes candidates in this order.
_SLOTS: tuple[_ProviderSlot, ...] = (
    _ProviderSlot(
        tier=ModelTier.FREE,
        api_key_env="MD_GEMINI_API_KEY",
        model_env="MD_GEMINI_MODEL",
        default_model="gemini-1.5-flash",
        build=lambda model, tier, api_key: GeminiProvider(
            model=model, tier=tier, api_key=api_key
        ),
        mock_reply="[free tier] Done.",
    ),
    _ProviderSlot(
        tier=ModelTier.STANDARD,
        api_key_env="MD_OPENAI_API_KEY",
        model_env="MD_OPENAI_MODEL",
        default_model="gpt-4o-mini",
        build=lambda model, tier, api_key: OpenAIProvider(
            model=model, tier=tier, api_key=api_key
        ),
        mock_reply="[standard tier] Done.",
    ),
    _ProviderSlot(
        tier=ModelTier.PREMIUM,
        api_key_env="MD_ANTHROPIC_API_KEY",
        model_env="MD_ANTHROPIC_MODEL",
        default_model="claude-opus-4-8",
        build=lambda model, tier, api_key: AnthropicProvider(
            model=model, tier=tier, api_key=api_key
        ),
        mock_reply="[premium tier] Reasoned answer.",
    ),
)


def _register_providers(registry: ProviderRegistry) -> None:
    """Register one provider per :data:`_SLOTS` entry, live where keyed.

    Algorithm:
        For each slot, read its API key env var. If set, construct the real
        adapter with the configured (or default) model id and that key. If
        unset, register a keyless :class:`MockProvider` at the same tier so the
        routing ladder stays fully populated regardless of which keys are set.
    """
    for slot in _SLOTS:
        api_key = os.environ.get(slot.api_key_env)
        if api_key:
            model = os.environ.get(slot.model_env, slot.default_model)
            registry.register(slot.build(model, slot.tier, api_key))
        else:
            registry.register(
                MockProvider(
                    f"mock:{slot.tier.name.lower()}",
                    tier=slot.tier,
                    reply=slot.mock_reply,
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
        tenant_id: Stable identifier for the calling tenant — the verified
            Firebase Auth ``uid`` when auth is enforced, or the request's
            declared ``tenant_id`` in dev mode. See :mod:`_lib.auth`.

    Returns:
        A zero-setup :class:`TenantContext` carrying the default quota, so a
        brand-new tenant starts on the shared free capacity (onboarding Stage 1).
    """
    return TenantContext(
        tenant_id=TenantId(tenant_id),
        quota=_DEFAULT_QUOTA,
        is_zero_setup=True,
    )
