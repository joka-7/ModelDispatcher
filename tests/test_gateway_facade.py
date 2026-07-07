"""Contract tests for the public facade and top-level API surface."""

from __future__ import annotations

import inspect

import model_dispatcher as md
from model_dispatcher import CompletionRequest, GatewaySettings, ModelGateway
from model_dispatcher.config import RoutingPolicy
from model_dispatcher.types import ModelTier, TaskComplexity


def test_public_api_reexports_core_symbols() -> None:
    for name in ("ModelGateway", "CompletionRequest", "QuotaExceededError"):
        assert name in md.__all__
        assert hasattr(md, name)


def test_gateway_exposes_sync_and_async_dispatch() -> None:
    assert hasattr(ModelGateway, "dispatch")
    assert inspect.iscoroutinefunction(ModelGateway.adispatch)
    assert not inspect.iscoroutinefunction(ModelGateway.dispatch)


def test_default_routing_policy_escalates_by_complexity() -> None:
    policy = RoutingPolicy()
    floor = policy.complexity_floor
    assert floor[TaskComplexity.TRIVIAL] == ModelTier.FREE
    assert floor[TaskComplexity.COMPLEX] == ModelTier.PREMIUM
    # Monotonic: higher complexity never maps to a cheaper floor.
    ordered = [floor[c] for c in sorted(TaskComplexity)]
    assert ordered == sorted(ordered)


def test_settings_defaults_are_constructible() -> None:
    settings = GatewaySettings()
    assert settings.max_iterations > 0
    assert settings.retry_max_attempts > 0


def test_completion_request_is_frozen(simple_request: CompletionRequest) -> None:
    import dataclasses

    try:
        simple_request.tenant = "other"  # type: ignore[misc]
    except dataclasses.FrozenInstanceError:
        return
    raise AssertionError("CompletionRequest must be immutable")
