"""Registry and lookup for provider strategies.

The registry is the only component that knows the concrete set of available
providers. Routing queries it by tier and capability; everything else holds
:class:`ModelProvider` references handed out from here.
"""

from __future__ import annotations

from ..types import ModelTier, ProviderCapability
from .base import ModelProvider

__all__ = ["ProviderRegistry"]


class ProviderRegistry:
    """An ordered collection of registered provider strategies.

    Internally keyed by ``name`` for identity lookups and indexed by tier for the
    router's cheapest-first queries.
    """

    def __init__(self) -> None:
        self._by_name: dict[str, ModelProvider] = {}

    def register(self, provider: ModelProvider) -> None:
        """Add a provider, replacing any existing one with the same name."""
        raise NotImplementedError

    def get(self, name: str) -> ModelProvider:
        """Return the provider registered under ``name``.

        Raises:
            KeyError: If no provider is registered under that name.
        """
        raise NotImplementedError

    def by_tier(self, tier: ModelTier) -> list[ModelProvider]:
        """Return all providers occupying exactly ``tier``."""
        raise NotImplementedError

    def at_or_above(self, floor: ModelTier) -> list[ModelProvider]:
        """Return providers whose tier is ``>= floor``, sorted cheapest-first.

        This is the primitive the router composes into a fallback candidate list.
        """
        raise NotImplementedError

    def cheapest_capable(
        self, floor: ModelTier, required: ProviderCapability
    ) -> ModelProvider:
        """Return the lowest-tier provider meeting ``floor`` and ``required`` caps.

        Raises:
            LookupError: If no registered provider satisfies the constraints.
        """
        raise NotImplementedError
