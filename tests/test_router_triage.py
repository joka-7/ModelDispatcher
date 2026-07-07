"""Contract tests for tier ordering and routing/triage wiring."""

from __future__ import annotations

from model_dispatcher.routing import ModelRouter, TaskTriage
from model_dispatcher.types import ModelTier, TaskComplexity


def test_model_tier_orders_cheapest_first() -> None:
    ordered = sorted(ModelTier)
    assert ordered == [
        ModelTier.FREE,
        ModelTier.CHEAP,
        ModelTier.STANDARD,
        ModelTier.PREMIUM,
    ]
    assert ModelTier.PREMIUM > ModelTier.FREE


def test_task_complexity_is_orderable() -> None:
    assert TaskComplexity.COMPLEX > TaskComplexity.TRIVIAL
    assert min(TaskComplexity) is TaskComplexity.TRIVIAL


def test_routing_symbols_are_importable() -> None:
    # Wiring smoke test: the public routing surface is constructible-shaped.
    assert callable(TaskTriage)
    assert callable(ModelRouter)
