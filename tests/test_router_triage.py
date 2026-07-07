"""Behavioral tests for triage classification and cost-tier routing."""

from __future__ import annotations

from model_dispatcher import (
    CompletionRequest,
    Message,
    ModelTier,
    ProviderCapability,
    ProviderRegistry,
    Role,
    TaskComplexity,
    TenantId,
    ToolSpec,
)
from model_dispatcher.config import RoutingPolicy
from model_dispatcher.providers import MockProvider
from model_dispatcher.routing import ModelRouter, TaskTriage


def _request(text: str, **kwargs: object) -> CompletionRequest:
    return CompletionRequest(
        messages=(Message(role=Role.USER, content=text),),
        tenant=TenantId("t"),
        **kwargs,  # type: ignore[arg-type]
    )


def test_triage_scores_trivial_vs_complex() -> None:
    triage = TaskTriage()
    assert triage.classify(_request("hi")) is TaskComplexity.TRIVIAL
    complex_prompt = (
        "Design and architect a distributed algorithm, then prove its correctness "
        "step by step and analyze the trade-offs. " * 4
    )
    assert triage.classify(_request(complex_prompt)) is TaskComplexity.COMPLEX


def test_router_routes_cheap_first_and_filters_by_capability() -> None:
    registry = ProviderRegistry()
    free = MockProvider("free", tier=ModelTier.FREE)
    cheap = MockProvider("cheap", tier=ModelTier.CHEAP)
    premium_no_tools = MockProvider(
        "premium", tier=ModelTier.PREMIUM, capabilities=ProviderCapability.NONE
    )
    for provider in (premium_no_tools, cheap, free):
        registry.register(provider)
    router = ModelRouter(registry, RoutingPolicy())

    # Trivial task, no tools -> candidates ordered cheapest-first from the floor.
    candidates = router.route(_request("hi"), TaskComplexity.TRIVIAL)
    assert [p.tier for p in candidates] == sorted(p.tier for p in candidates)
    assert candidates[0].tier is ModelTier.FREE

    # A tool-bearing request excludes the premium provider that lacks TOOLS.
    tool = ToolSpec(name="t", description="d", parameters={"type": "object"})
    tool_request = _request("use a tool", tools=(tool,))
    tool_candidates = router.route(tool_request, TaskComplexity.TRIVIAL)
    assert "premium" not in [p.name for p in tool_candidates]


def test_complex_task_reserves_premium_floor() -> None:
    registry = ProviderRegistry()
    registry.register(MockProvider("free", tier=ModelTier.FREE))
    registry.register(MockProvider("premium", tier=ModelTier.PREMIUM))
    router = ModelRouter(registry, RoutingPolicy())

    candidates = router.route(_request("anything"), TaskComplexity.COMPLEX)
    # COMPLEX floors at PREMIUM, so the FREE provider is not a candidate.
    assert [p.name for p in candidates] == ["premium"]
