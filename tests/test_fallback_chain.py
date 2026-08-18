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
from model_dispatcher.exceptions import AllProvidersExhausted, AuthenticationError
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


# -- Pooled-credential rotation (a tenant with several keys for one provider) #


def test_pooled_keys_rotate_on_the_same_provider_before_falling_back(
    make_gateway: Callable[..., ModelGateway],
    make_tenant: Callable[..., TenantContext],
) -> None:
    provider = MockProvider(
        "mock:free",
        tier=ModelTier.FREE,
        fail_times=1,
        fail_with=ErrorClass.RATE_LIMIT,
        reply="via key 2",
    )
    other = MockProvider("mock:cheap", tier=ModelTier.CHEAP, reply="should not run")
    gateway = make_gateway(provider, other)
    tenant = make_tenant(**{"user_key:mock": "aaaa1111, bbbb2222"})

    result = gateway.dispatch(_request(tenant), tenant)

    assert result.final_message.content == "via key 2"
    # Both attempts stayed on the same provider — no fallback to `other` needed.
    assert [a.provider_name for a in result.steps[0].attempts] == [
        "mock:free",
        "mock:free",
    ]
    # The actual raw key differed per attempt, proving real rotation (not a
    # blind retry with the same credential).
    assert provider.received_api_keys == ["aaaa1111", "bbbb2222"]
    # ...and the audit trail only ever carries the masked reference.
    assert [a.credential_ref for a in result.steps[0].attempts] == [
        "****1111",
        "****2222",
    ]


def test_auth_failure_on_one_pooled_key_tries_the_next_before_stopping(
    make_gateway: Callable[..., ModelGateway],
    make_tenant: Callable[..., TenantContext],
) -> None:
    """A revoked/bad key shouldn't doom a sibling key that's still valid."""
    provider = MockProvider(
        "mock:free",
        tier=ModelTier.FREE,
        fail_times=1,
        fail_with=ErrorClass.AUTH,
        reply="via good key",
    )
    gateway = make_gateway(provider)
    tenant = make_tenant(**{"user_key:mock": "bad-key,good-key"})

    result = gateway.dispatch(_request(tenant), tenant)

    assert result.final_message.content == "via good key"
    assert provider.received_api_keys == ["bad-key", "good-key"]


def test_auth_failure_stops_the_dispatch_once_no_pooled_keys_remain(
    make_gateway: Callable[..., ModelGateway],
    make_tenant: Callable[..., TenantContext],
) -> None:
    """Unchanged from single-key behaviour: a terminal failure with no other
    key left to try aborts the whole dispatch rather than trying another
    provider candidate."""
    provider = MockProvider(
        "mock:free", tier=ModelTier.FREE, fail_times=99, fail_with=ErrorClass.AUTH
    )
    other = MockProvider("mock:cheap", tier=ModelTier.CHEAP, reply="never reached")
    gateway = make_gateway(provider, other)
    tenant = make_tenant(**{"user_key:mock": "only-key"})

    with pytest.raises(AuthenticationError):
        gateway.dispatch(_request(tenant), tenant)


def test_condition_predicates_partition_error_classes() -> None:
    assert is_retryable(ErrorClass.TRANSIENT)
    assert is_fallback_worthy(ErrorClass.RATE_LIMIT)
    assert is_fallback_worthy(ErrorClass.QUOTA)
    assert is_terminal(ErrorClass.AUTH)
    assert not is_terminal(ErrorClass.RATE_LIMIT)
    assert not is_retryable(ErrorClass.AUTH)
