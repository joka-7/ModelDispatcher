"""Shared fixtures for the behavioral test-suite.

These tests exercise real runtime behavior of the gateway using the keyless
:class:`MockProvider`, so routing, fallback, quota, the agent loop, and the
onboarding handoff are all driven end-to-end without any network or API keys.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from model_dispatcher import (
    CompletionRequest,
    Message,
    ModelGateway,
    ProviderRegistry,
    Role,
    TenantContext,
    TenantId,
    TenantQuota,
)


@pytest.fixture
def tenant_id() -> TenantId:
    """A throwaway tenant identity."""
    return TenantId("tenant-test")


@pytest.fixture
def simple_request(tenant_id: TenantId) -> CompletionRequest:
    """A minimal, tool-free completion request."""
    return CompletionRequest(
        messages=(Message(role=Role.USER, content="hello"),),
        tenant=tenant_id,
    )


@pytest.fixture
def make_tenant() -> Callable[..., TenantContext]:
    """Return a factory building tenants with generous default quotas."""

    def _make(
        tenant_id: str = "tenant-test",
        *,
        requests_per_min: int = 1_000,
        tokens_per_min: int = 1_000_000,
        tokens_per_day: int = 10_000_000,
        is_zero_setup: bool = True,
        **metadata: str,
    ) -> TenantContext:
        return TenantContext(
            tenant_id=TenantId(tenant_id),
            quota=TenantQuota(
                requests_per_min=requests_per_min,
                tokens_per_min=tokens_per_min,
                tokens_per_day=tokens_per_day,
            ),
            is_zero_setup=is_zero_setup,
            metadata=metadata,
        )

    return _make


@pytest.fixture
def make_gateway() -> Callable[..., ModelGateway]:
    """Return a factory assembling a gateway from a set of providers."""

    def _make(*providers: object) -> ModelGateway:
        registry = ProviderRegistry()
        for provider in providers:
            registry.register(provider)  # type: ignore[arg-type]
        return ModelGateway.create(registry)

    return _make
