"""Contract tests for the fallback chain-of-responsibility wiring."""

from __future__ import annotations

from model_dispatcher.exceptions import (
    AllProvidersExhausted,
    ModelDispatcherError,
    QuotaExceededError,
)
from model_dispatcher.fallback import HandlerOutcome, InvocationContext
from model_dispatcher.onboarding.handoff import HandoffAction, HandoffResponse


def test_handler_outcomes_are_distinct() -> None:
    members = {
        HandlerOutcome.CONTINUE,
        HandlerOutcome.SUCCESS,
        HandlerOutcome.FALLBACK,
        HandlerOutcome.STOP,
    }
    assert len(members) == 4


def test_invocation_context_seeds_from_candidates() -> None:
    ctx = InvocationContext(request=None, candidates=[])  # type: ignore[arg-type]
    assert ctx.candidates == []
    assert ctx.response is None
    assert ctx.attempts == []


def test_exhaustion_and_quota_errors_carry_http_status() -> None:
    exhausted = AllProvidersExhausted("no candidates left")
    assert exhausted.http_status == 503
    assert isinstance(exhausted, ModelDispatcherError)

    handoff = HandoffResponse(
        error="quota_exceeded",
        provider="openai",
        action=HandoffAction.TRIGGER_KEY_WIZARD,
        http_status=429,
    )
    err = QuotaExceededError(handoff)
    assert err.http_status == 429
    assert err.handoff.provider == "openai"
