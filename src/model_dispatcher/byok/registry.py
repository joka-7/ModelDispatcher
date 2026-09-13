"""Registry building for a server pooling its own keys with visitor BYOK keys.

The pattern this generalises: a single backend serves every visitor from
behind one origin. A server operator can configure a shared key per vendor
(env vars), and/or a visitor can paste in their own key(s) for the AI
settings panel to send with the request instead. Either is sufficient on its
own; both can be present at once, for different vendors or the same one
(:class:`~model_dispatcher.security.credentials.CredentialResolver` prefers
the caller's own key over the shared one for a given vendor).

Extracted from four independent apps built on top of ``model_dispatcher``
that had each hand-written this exact wiring (env var lookup, skip-if-keyless,
the ``user_key:<family>`` metadata shape) around the same
:class:`~model_dispatcher.providers.registry.ProviderRegistry` and
:class:`~model_dispatcher.security.credentials.CredentialResolver`.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from ..exceptions import NoProviderAvailableError
from ..providers.base import ModelProvider
from ..providers.registry import ProviderRegistry

__all__ = [
    "ProviderSpec",
    "build_registry",
    "credential_metadata",
    "configured_providers",
]


class _ProviderFactory(Protocol):
    """The constructor shape every built-in provider adapter has.

    Keyword-only ``model`` and ``api_key``. Structural, not
    ``type[ModelProvider]``, since the base class itself declares no
    ``__init__`` of that shape.
    """

    def __call__(self, *, model: str, api_key: str | None = None) -> ModelProvider: ...


@dataclass(frozen=True, slots=True)
class ProviderSpec:
    """One vendor's wiring: how to build it, and where its config lives.

    Attributes:
        provider_cls: The :class:`ModelProvider` adapter to construct.
        key_env_var: Env var holding this server's shared key, if any.
        model_env_var: Env var overriding ``default_model``, if set.
        default_model: Model to use when ``model_env_var`` is unset.
    """

    provider_cls: _ProviderFactory
    key_env_var: str
    model_env_var: str
    default_model: str


def configured_providers(specs: Mapping[str, ProviderSpec]) -> frozenset[str]:
    """Vendor names backed by a server-side key (env var), regardless of BYOK.

    For an AI settings UI to tell a visitor "no key needed for this one"
    versus "bring your own", per vendor.
    """
    return frozenset(
        name for name, spec in specs.items() if os.environ.get(spec.key_env_var)
    )


def credential_metadata(credentials: Mapping[str, Sequence[str]]) -> dict[str, str]:
    """Map a vendor -> keys mapping to tenant metadata credentials reads.

    ``{vendor: [key, ...]}`` becomes the ``user_key:<family>`` shape
    :class:`~model_dispatcher.security.credentials.CredentialResolver` reads
    (comma-joined pooling of more than one key per vendor).
    """
    return {
        f"user_key:{name}": ",".join(keys) for name, keys in credentials.items() if keys
    }


def build_registry(
    specs: Mapping[str, ProviderSpec],
    credentials: Mapping[str, Sequence[str]],
) -> ProviderRegistry:
    """Register only the vendors with *some* usable key for this request.

    A vendor gets a server key, a visitor key, both, or neither -- "neither"
    leaves it out of the registry entirely. This matters because
    :class:`~model_dispatcher.security.credentials.CredentialResolver`
    treats a missing credential as terminal, not fallback-worthy: a keyless
    vendor sitting in the registry ahead of one the visitor actually gave a
    key for would otherwise hard-fail the request before ever reaching the
    candidate that would have worked.

    Raises:
        NoProviderAvailableError: If no vendor in ``specs`` has a server key
            or a visitor-supplied credential -- callers should treat this as
            a fast, cheap error rather than let a doomed request reach
            :meth:`~model_dispatcher.gateway.ModelGateway.dispatch`.
    """
    registry = ProviderRegistry()
    for name, spec in specs.items():
        server_key = os.environ.get(spec.key_env_var)
        if not server_key and not credentials.get(name):
            continue
        model = os.environ.get(spec.model_env_var) or spec.default_model
        registry.register(spec.provider_cls(model=model, api_key=server_key))

    if not len(registry):
        raise NoProviderAvailableError(
            "no provider key available -- set one on the server or supply your own"
        )
    return registry
