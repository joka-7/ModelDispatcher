"""Server-hosted BYOK integration: pooled server keys plus visitor keys.

For an app that runs its own backend (no separate client package needed --
frontend and this backend share an origin) and wants to mix a server
operator's own pooled key per vendor with a visitor's bring-your-own key,
behind one AI settings panel. Extracted from real apps that had each
hand-built this same registry-building, credential-metadata, and
timeout-bounded-dispatch wiring around the plain :class:`ModelGateway`.

Not re-exported from the top-level ``model_dispatcher`` package (same
convention as ``security``/``routing``/``fallback``) -- import from here.
"""

from __future__ import annotations

from .dispatch import adispatch_with_timeout, dispatch_with_timeout
from .registry import (
    ProviderSpec,
    build_registry,
    configured_providers,
    credential_metadata,
)

__all__ = [
    "ProviderSpec",
    "build_registry",
    "credential_metadata",
    "configured_providers",
    "dispatch_with_timeout",
    "adispatch_with_timeout",
]
