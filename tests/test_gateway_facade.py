"""Behavioral tests for the public facade, perimeter, and API surface."""

from __future__ import annotations

import inspect
from collections.abc import Callable

import pytest

import model_dispatcher as md
from model_dispatcher import (
    CompletionRequest,
    GatewaySettings,
    Message,
    ModelGateway,
    ModelTier,
    Role,
    StopReason,
    TenantContext,
)
from model_dispatcher.config import RoutingPolicy, SecuritySettings
from model_dispatcher.exceptions import PerimeterViolation
from model_dispatcher.providers import MockProvider
from model_dispatcher.types import ModelTier as Tier
from model_dispatcher.types import TaskComplexity


def _request(tenant: TenantContext, text: str = "hello world") -> CompletionRequest:
    return CompletionRequest(
        messages=(Message(role=Role.USER, content=text),),
        tenant=tenant.tenant_id,
    )


def test_public_api_reexports_core_symbols() -> None:
    for name in ("ModelGateway", "CompletionRequest", "QuotaExceededError"):
        assert name in md.__all__
        assert hasattr(md, name)


def test_gateway_exposes_sync_and_async_dispatch() -> None:
    assert inspect.iscoroutinefunction(ModelGateway.adispatch)
    assert not inspect.iscoroutinefunction(ModelGateway.dispatch)


def test_end_to_end_dispatch_returns_completion(
    make_gateway: Callable[..., ModelGateway],
    make_tenant: Callable[..., TenantContext],
) -> None:
    gateway = make_gateway(MockProvider("mock:free", tier=ModelTier.FREE, reply="hi!"))
    tenant = make_tenant()
    result = gateway.dispatch(_request(tenant), tenant)
    assert result.stop_reason is StopReason.COMPLETED
    assert result.final_message.content == "hi!"


async def test_async_dispatch_matches_sync(
    make_gateway: Callable[..., ModelGateway],
    make_tenant: Callable[..., TenantContext],
) -> None:
    gateway = make_gateway(MockProvider("mock:free", tier=ModelTier.FREE, reply="yo"))
    tenant = make_tenant()
    result = await gateway.adispatch(_request(tenant), tenant)
    assert result.final_message.content == "yo"


def test_perimeter_rejects_oversized_payload(
    make_tenant: Callable[..., TenantContext],
) -> None:
    registry = md.ProviderRegistry()
    registry.register(MockProvider("mock:free", tier=ModelTier.FREE))
    settings = GatewaySettings(security=SecuritySettings(max_payload_bytes=10))
    gateway = ModelGateway.create(registry, settings=settings)
    tenant = make_tenant()

    with pytest.raises(PerimeterViolation) as excinfo:
        gateway.dispatch(_request(tenant, "x" * 500), tenant)
    assert excinfo.value.http_status == 403


def test_default_routing_policy_escalates_by_complexity() -> None:
    floor = RoutingPolicy().complexity_floor
    assert floor[TaskComplexity.TRIVIAL] is Tier.FREE
    assert floor[TaskComplexity.COMPLEX] is Tier.PREMIUM
    ordered = [floor[c] for c in sorted(TaskComplexity)]
    assert ordered == sorted(ordered)  # monotonic
