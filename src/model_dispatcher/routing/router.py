"""Cost-aware model router.

The router is the second half of triage: it turns a :class:`TaskComplexity`
verdict into an *ordered list of candidate providers*. That ordered list is
handed straight to the fallback chain, so "routing" and "fallback ordering" are
the same decision expressed once.
"""

from __future__ import annotations

from ..config import RoutingPolicy
from ..providers.base import ModelProvider
from ..providers.registry import ProviderRegistry
from ..types import CompletionRequest, ProviderCapability, TaskComplexity

__all__ = ["ModelRouter"]


class ModelRouter:
    """Selects and orders candidate providers for a request."""

    def __init__(self, registry: ProviderRegistry, policy: RoutingPolicy) -> None:
        self._registry = registry
        self._policy = policy

    def route(
        self, request: CompletionRequest, complexity: TaskComplexity
    ) -> list[ModelProvider]:
        """Return an ordered, cheapest-first list of candidate providers.

        Algorithm:
            1. Look up the tier *floor* for ``complexity`` in the routing policy;
               a caller ``tier_hint`` may raise (never lower) that floor.
            2. Derive the :class:`ProviderCapability` the request requires (e.g.
               ``TOOLS`` when tools are present) and filter candidates by it.
            3. Collect providers at or above the floor via the registry, sorted
               ascending by tier so the cheapest capable model is tried first.
            4. If ``policy.allow_escalation`` is false, keep only the floor tier;
               otherwise retain the escalating tail so fallback can climb.
            5. Truncate to ``policy.max_candidates``.

        The result seeds the fallback chain's ``candidates`` list.
        """
        raise NotImplementedError

    def _required_capabilities(self, request: CompletionRequest) -> ProviderCapability:
        """Derive the capability mask a request demands (tools, vision, ...)."""
        raise NotImplementedError
