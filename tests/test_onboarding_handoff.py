"""Behavioral tests for the two-stage onboarding flow and Stage-2 handoff."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

import pytest

from model_dispatcher import (
    CompletionRequest,
    Message,
    ModelGateway,
    ModelTier,
    OnboardingStage,
    Role,
    TenantContext,
)
from model_dispatcher.exceptions import QuotaExceededError
from model_dispatcher.onboarding.flow import OnboardingResolver
from model_dispatcher.onboarding.handoff import (
    HandoffAction,
    HandoffResponse,
    KeyWizardHandoff,
)
from model_dispatcher.providers import MockProvider


def _sample_handoff() -> HandoffResponse:
    return HandoffResponse(
        error="quota_exceeded",
        provider="openai",
        action=HandoffAction.TRIGGER_KEY_WIZARD,
        http_status=402,
    )


def _request(tenant: TenantContext) -> CompletionRequest:
    return CompletionRequest(
        messages=(Message(role=Role.USER, content="hello there"),),
        tenant=tenant.tenant_id,
    )


def test_handoff_payload_matches_contract() -> None:
    payload = _sample_handoff().to_payload()
    assert payload == {
        "error": "quota_exceeded",
        "provider": "openai",
        "action": "trigger_key_wizard",
    }


def test_handoff_status_codes_are_402_or_429() -> None:
    budget = _sample_handoff()
    rate = replace(budget, http_status=429)
    assert budget.http_status in {402, 429}
    assert rate.http_status in {402, 429}


def test_key_wizard_builds_rate_window_and_budget_variants() -> None:
    wizard = KeyWizardHandoff()
    assert wizard.build("openai", rate_window=True).http_status == 429
    assert wizard.build("openai", rate_window=False).http_status == 402


def test_resolver_reports_stage_by_tenant(
    make_tenant: Callable[..., TenantContext],
) -> None:
    resolver = OnboardingResolver(KeyWizardHandoff())
    zero_setup = make_tenant(is_zero_setup=True)
    byo_key = make_tenant(is_zero_setup=False)
    assert resolver.stage(zero_setup) is OnboardingStage.ZERO_SETUP
    assert resolver.stage(byo_key) is OnboardingStage.GUIDED_HANDOFF


def test_quota_exceeded_raises_stage2_handoff_end_to_end(
    make_gateway: Callable[..., ModelGateway],
    make_tenant: Callable[..., TenantContext],
) -> None:
    provider = MockProvider("mock:free", tier=ModelTier.FREE, reply="ok")
    gateway = make_gateway(provider)
    # Quota so tight the pre-flight estimate cannot fit -> DENY, no cheaper option.
    tenant = make_tenant(
        tokens_per_min=1, tokens_per_day=1, requests_per_min=1, is_zero_setup=True
    )

    with pytest.raises(QuotaExceededError) as excinfo:
        gateway.dispatch(_request(tenant), tenant)

    err = excinfo.value
    assert err.http_status in {402, 429}
    payload = err.to_payload()
    assert payload["error"] == "quota_exceeded"
    assert payload["action"] == "trigger_key_wizard"
    assert payload["provider"] == "mock:free"
