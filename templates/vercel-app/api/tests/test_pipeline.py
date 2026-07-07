"""Behavioural tests for the gateway wrapper's dispatch pipeline.

Run on Python >= 3.12 (the library's floor) with the library installed:

    pip install -e .            # from the repo root, installs model-dispatcher
    pytest templates/vercel-app/api/tests
"""

from __future__ import annotations

import json

from _lib.appcheck import (
    AppCheckClaims,
    FirebaseAppCheckVerifier,
    NoopAppCheckVerifier,
)
from _lib.pipeline import run_dispatch

from model_dispatcher.exceptions import QuotaExceededError
from model_dispatcher.onboarding.handoff import HandoffAction, HandoffResponse

_BODY = json.dumps({"prompt": "hello", "tenant_id": "t-1"}).encode()


def test_missing_app_check_is_rejected_before_the_gateway() -> None:
    """A missing token yields 403 and the gateway is never built or called."""
    built = False

    def spy_factory() -> object:
        nonlocal built
        built = True
        raise AssertionError("gateway must not be invoked when App Check fails")

    status, body = run_dispatch(
        app_check_token=None,
        raw_body=_BODY,
        verifier=FirebaseAppCheckVerifier(),
        gateway_factory=spy_factory,  # type: ignore[arg-type]
    )

    assert status == 403
    assert body == {"error": "app_check_failed"}
    assert built is False


def test_happy_path_returns_200_and_a_trace() -> None:
    """With App Check bypassed and the mock providers, a dispatch completes."""
    status, body = run_dispatch(
        app_check_token="ignored",
        raw_body=_BODY,
        verifier=NoopAppCheckVerifier(),
    )

    assert status == 200
    assert "final" in body
    assert body["stop_reason"]


def test_bad_body_returns_400() -> None:
    """An empty prompt fails validation before the gateway runs."""
    status, body = run_dispatch(
        app_check_token="ignored",
        raw_body=json.dumps({"prompt": "  "}).encode(),
        verifier=NoopAppCheckVerifier(),
    )

    assert status == 400
    assert body["error"] == "bad_request"


def test_quota_breach_maps_to_the_trigger_key_wizard_handoff() -> None:
    """A QuotaExceededError becomes the 402/429 trigger_key_wizard contract."""

    class _WizardGateway:
        def dispatch(self, *_args: object, **_kwargs: object) -> object:
            handoff = HandoffResponse(
                error="quota_exceeded",
                provider="openai",
                action=HandoffAction.TRIGGER_KEY_WIZARD,
                http_status=402,
            )
            raise QuotaExceededError(handoff)

    status, body = run_dispatch(
        app_check_token="ignored",
        raw_body=_BODY,
        verifier=NoopAppCheckVerifier(),
        gateway_factory=_WizardGateway,  # type: ignore[arg-type]
    )

    assert status == 402
    assert body["action"] == "trigger_key_wizard"
    assert body["provider"] == "openai"


def test_firebase_verifier_normalises_claims() -> None:
    """The Noop strategy yields placeholder claims without any verification."""
    claims = NoopAppCheckVerifier().verify(None)
    assert isinstance(claims, AppCheckClaims)
    assert claims.app_id == "dev-bypass"
