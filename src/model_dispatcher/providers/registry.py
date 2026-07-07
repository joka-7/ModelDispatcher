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
    router's cheapest-first queries. Insertion order is preserved so that
    equally-ranked providers fall back in a deterministic sequence.
    """

    def __init__(self) -> None:
        self._by_name: dict[str, ModelProvider] = {}

    def __len__(self) -> int:
        """Return the number of registered providers."""
        return len(self._by_name)

    def __contains__(self, name: object) -> bool:
        """Return whether a provider is registered under ``name``."""
        return name in self._by_name

    def register(self, provider: ModelProvider) -> None:
        """Add a provider, replacing any existing one with the same name."""
        self._by_name[provider.name] = provider

    def get(self, name: str) -> ModelProvider:
        """Return the provider registered under ``name``.

        Raises:
            KeyError: If no provider is registered under that name.
        """
        return self._by_name[name]

    def all(self) -> list[ModelProvider]:
        """Return every registered provider in insertion order."""
        return list(self._by_name.values())

    def by_tier(self, tier: ModelTier) -> list[ModelProvider]:
        """Return all providers occupying exactly ``tier``, in insertion order."""
        return [p for p in self._by_name.values() if p.tier == tier]

    def at_or_above(self, floor: ModelTier) -> list[ModelProvider]:
        """Return providers whose tier is ``>= floor``, sorted cheapest-first.

        Ties (same tier) preserve registration order via a stable sort, so the
        fallback sequence within a tier is deterministic.
        """
        eligible = [p for p in self._by_name.values() if p.tier >= floor]
        return sorted(eligible, key=lambda p: p.tier)

    def cheapest_capable(
        self, floor: ModelTier, required: ProviderCapability
    ) -> ModelProvider:
        """Return the lowest-tier provider meeting ``floor`` and ``required`` caps.

        Raises:
            LookupError: If no registered provider satisfies the constraints.
        """
        for provider in self.at_or_above(floor):
            if required & provider.capabilities == required:
                return provider
        raise LookupError(
            f"no provider at tier >= {floor.name} with capabilities {required!r}"
        )
