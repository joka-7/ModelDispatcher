"""Behavioral tests for token-aware quota reservation and reconciliation."""

from __future__ import annotations

from model_dispatcher import InMemoryQuotaStore, ModelTier, TenantContext, TenantId
from model_dispatcher.providers import MockProvider
from model_dispatcher.quota import QuotaManager, QuotaOutcome, TenantQuota
from model_dispatcher.quota.store import QuotaStore
from model_dispatcher.types import Usage


def _tenant(**limits: int) -> TenantContext:
    return TenantContext(
        tenant_id=TenantId("t"),
        quota=TenantQuota(
            requests_per_min=limits.get("requests_per_min", 100),
            tokens_per_min=limits.get("tokens_per_min", 10_000),
            tokens_per_day=limits.get("tokens_per_day", 100_000),
        ),
    )


def test_usage_totals_and_accumulates() -> None:
    a = Usage(prompt_tokens=10, completion_tokens=5)
    b = Usage(prompt_tokens=3, completion_tokens=7)
    assert a.total_tokens == 15
    assert (a + b).total_tokens == 25


def test_in_memory_store_satisfies_protocol() -> None:
    assert isinstance(InMemoryQuotaStore(), QuotaStore)


def test_reserve_allows_within_budget_and_denies_over() -> None:
    manager = QuotaManager(InMemoryQuotaStore())
    provider = MockProvider("mock", tier=ModelTier.FREE)
    tenant = _tenant(tokens_per_min=1_000)

    allow = manager.reserve(tenant, 100, provider)
    assert allow.outcome is QuotaOutcome.ALLOW
    assert allow.reserved_tokens == 100

    deny = manager.reserve(tenant, 5_000, provider)
    assert deny.outcome is QuotaOutcome.DENY
    assert deny.breached_window == "tokens_per_min"


def test_soft_limit_warns_before_hard_deny() -> None:
    manager = QuotaManager(InMemoryQuotaStore())
    provider = MockProvider("mock", tier=ModelTier.FREE)
    tenant = _tenant(tokens_per_min=100)  # soft_limit_ratio default 0.9

    decision = manager.reserve(tenant, 95, provider)
    assert decision.outcome is QuotaOutcome.SOFT_LIMIT
    assert decision.breached_window == "tokens_per_min"


def test_commit_reconciles_estimate_against_actual() -> None:
    store = InMemoryQuotaStore()
    manager = QuotaManager(store)
    provider = MockProvider("mock", tier=ModelTier.FREE)
    tenant = _tenant(tokens_per_min=10_000)

    decision = manager.reserve(tenant, 100, provider)  # pre-charge 100
    assert store.read(tenant.tenant_id, "tokens_per_min") == 100

    # Actual usage came in lower than the estimate: the delta is refunded.
    manager.commit(tenant, decision, Usage(prompt_tokens=40, completion_tokens=20))
    assert store.read(tenant.tenant_id, "tokens_per_min") == 60
