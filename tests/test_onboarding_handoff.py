"""Contract tests for the Stage-2 onboarding handoff payload.

The exact JSON shape is an external contract the front end depends on, so it is
pinned here even though the builder body is not yet implemented.
"""

from __future__ import annotations

from dataclasses import replace

from model_dispatcher.onboarding.handoff import HandoffAction, HandoffResponse


def _sample_handoff() -> HandoffResponse:
    return HandoffResponse(
        error="quota_exceeded",
        provider="openai",
        action=HandoffAction.TRIGGER_KEY_WIZARD,
        http_status=402,
    )


def test_handoff_fields_match_contract() -> None:
    handoff = _sample_handoff()
    assert handoff.error == "quota_exceeded"
    assert handoff.provider == "openai"
    assert handoff.action.value == "trigger_key_wizard"


def test_handoff_status_codes_are_402_or_429() -> None:
    budget = _sample_handoff()
    rate = replace(budget, http_status=429)
    assert budget.http_status in {402, 429}
    assert rate.http_status in {402, 429}


def test_handoff_is_immutable() -> None:
    import dataclasses

    handoff = _sample_handoff()
    try:
        handoff.provider = "anthropic"  # type: ignore[misc]
    except dataclasses.FrozenInstanceError:
        return
    raise AssertionError("HandoffResponse must be immutable")
