"""Behavioral tests for chain-of-responsibility fallback and failover."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from model_dispatcher import (
    CompletionRequest,
    ErrorClass,
    Message,
    ModelGateway,
    ModelTier,
    Role,
    TenantContext,
)
from model_dispatcher.exceptions import AllProvidersExhausted
from model_dispatcher.fallback.conditions import (
    is_fallback_worthy,
    is_retryable,
    is_terminal,
)
from model_dispatcher.providers import MockProvider


def _request(tenant: TenantContext) -> CompletionRequest:
    return CompletionRequest(
        messages=(Message(role=Role.USER, content="hi"),),
        tenant=tenant.tenant_id,
    )


def test_rate_limited_provider_falls_back_to_next(
    make_gateway: Callable[..., ModelGateway],
    make_tenant: Callable[..., TenantContext],
) -> None:
    free = MockProvider(
        "mock:free", tier=ModelTier.FREE, fail_times=99, fail_with=ErrorClass.RATE_LIMIT
    )
    cheap = MockProvider("mock:cheap", tier=ModelTier.CHEAP, reply="served by cheap")
    gateway = make_gateway(free, cheap)
    tenant = make_tenant()

    result = gateway.dispatch(_request(tenant), tenant)

    assert result.final_message.content == "served by cheap"
    attempted = [a.provider_name for a in result.steps[0].attempts]
    assert attempted == ["mock:free", "mock:cheap"]


def test_transient_error_retries_same_provider_then_succeeds(
    make_gateway: Callable[..., ModelGateway],
    make_tenant: Callable[..., TenantContext],
) -> None:
    # Fails twice transiently, then succeeds on the third attempt (max_attempts=3).
    flaky = MockProvider(
        "mock:free",
        tier=ModelTier.FREE,
        fail_times=2,
        fail_with=ErrorClass.TRANSIENT,
        reply="recovered",
    )
    gateway = make_gateway(flaky)
    tenant = make_tenant()

    result = gateway.dispatch(_request(tenant), tenant)

    assert result.final_message.content == "recovered"
    # Two recorded transient failures precede the success on the same provider.
    errors = [a.error_class for a in result.steps[0].attempts if a.error_class]
    assert errors == [ErrorClass.TRANSIENT, ErrorClass.TRANSIENT]


def test_all_providers_exhausted_raises(
    make_gateway: Callable[..., ModelGateway],
    make_tenant: Callable[..., TenantContext],
) -> None:
    a = MockProvider("mock:a", tier=ModelTier.FREE, fail_times=99)
    b = MockProvider("mock:b", tier=ModelTier.CHEAP, fail_times=99)
    gateway = make_gateway(a, b)
    tenant = make_tenant()

    with pytest.raises(AllProvidersExhausted) as excinfo:
        gateway.dispatch(_request(tenant), tenant)
    assert excinfo.value.http_status == 503


def test_condition_predicates_partition_error_classes() -> None:
    assert is_retryable(ErrorClass.TRANSIENT)
    assert is_fallback_worthy(ErrorClass.RATE_LIMIT)
    assert is_fallback_worthy(ErrorClass.QUOTA)
    assert is_terminal(ErrorClass.AUTH)
    assert not is_terminal(ErrorClass.RATE_LIMIT)
    assert not is_retryable(ErrorClass.AUTH)
