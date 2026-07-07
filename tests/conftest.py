"""Shared fixtures for the structural test-suite.

These tests exercise the *contracts* of the skeleton (types compose, enums order,
the onboarding payload shape is stable, wiring is importable) — not runtime
behaviour, which the implementation phase will add. No network or provider SDKs
are touched.
"""

from __future__ import annotations

import pytest

from model_dispatcher.types import (
    CompletionRequest,
    Message,
    Role,
    TenantId,
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
