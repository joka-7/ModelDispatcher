"""Contract tests for quota value types and token accounting."""

from __future__ import annotations

from model_dispatcher.quota import InMemoryQuotaStore, QuotaOutcome, QuotaStore
from model_dispatcher.types import Usage


def test_usage_totals_and_accumulates() -> None:
    a = Usage(prompt_tokens=10, completion_tokens=5)
    b = Usage(prompt_tokens=3, completion_tokens=7)
    assert a.total_tokens == 15
    assert (a + b).total_tokens == 25


def test_quota_outcomes_cover_allow_soft_deny() -> None:
    assert {o.value for o in QuotaOutcome} == {"allow", "soft_limit", "deny"}


def test_in_memory_store_satisfies_protocol() -> None:
    store = InMemoryQuotaStore()
    # runtime_checkable Protocol: the concrete store must structurally match.
    assert isinstance(store, QuotaStore)
