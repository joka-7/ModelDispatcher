"""Behavioural tests for the gateway wrapper's dispatch pipeline.

Run on Python >= 3.11 (the library's floor) with the library installed:

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
from _lib.auth import AuthClaims, FirebaseAuthVerifier, NoopAuthVerifier
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
        authorization_header="Bearer ignored",
        raw_body=_BODY,
        verifier=FirebaseAppCheckVerifier(),
        auth_verifier=NoopAuthVerifier(),
        gateway_factory=spy_factory,  # type: ignore[arg-type]
    )

    assert status == 403
    assert body == {"error": "app_check_failed"}
    assert built is False


def test_missing_authorization_is_rejected_before_the_gateway() -> None:
    """A missing/invalid Authorization header yields 401 before dispatch runs.

    This is the guard that makes tenant identity authoritative: App Check alone
    only proves the request came from the real app, not who the caller is.
    """
    built = False

    def spy_factory() -> object:
        nonlocal built
        built = True
        raise AssertionError("gateway must not be invoked when auth fails")

    status, body = run_dispatch(
        app_check_token="ignored",
        authorization_header=None,
        raw_body=_BODY,
        verifier=NoopAppCheckVerifier(),
        auth_verifier=FirebaseAuthVerifier(),
        gateway_factory=spy_factory,  # type: ignore[arg-type]
    )

    assert status == 401
    assert body == {"error": "unauthenticated"}
    assert built is False


def test_happy_path_returns_200_and_a_trace_with_complexity() -> None:
    """With both guards bypassed and the mock providers, a dispatch completes."""
    status, body = run_dispatch(
        app_check_token="ignored",
        authorization_header="Bearer ignored",
        raw_body=_BODY,
        verifier=NoopAppCheckVerifier(),
        auth_verifier=NoopAuthVerifier(),
    )

    assert status == 200
    assert "final" in body
    assert body["stop_reason"]
    assert body["complexity"]


def test_verified_uid_overrides_a_spoofed_tenant_id() -> None:
    """A caller cannot pick their own tenant by lying in the request body.

    Once auth is enforced, the verified uid is the tenant id used for quota —
    the body's ``tenant_id`` is ignored, not merely a fallback default.
    """
    seen_tenant_ids: list[str] = []

    def spy_tenant_factory(tenant_id: str) -> object:
        seen_tenant_ids.append(tenant_id)
        from _lib.wiring import build_tenant

        return build_tenant(tenant_id)

    class _VerifiedAuth:
        def verify(self, header_value: str | None) -> AuthClaims:
            return AuthClaims(uid="verified-uid-123")

    body = json.dumps({"prompt": "hello", "tenant_id": "someone-elses-tenant"}).encode()
    status, _ = run_dispatch(
        app_check_token="ignored",
        authorization_header="Bearer real-token",
        raw_body=body,
        verifier=NoopAppCheckVerifier(),
        auth_verifier=_VerifiedAuth(),  # type: ignore[arg-type]
        tenant_factory=spy_tenant_factory,  # type: ignore[arg-type]
    )

    assert status == 200
    assert seen_tenant_ids == ["verified-uid-123"]


def test_disabled_auth_mode_falls_back_to_the_declared_tenant_id() -> None:
    """With auth disabled (dev mode), the request's own tenant_id is used."""
    seen_tenant_ids: list[str] = []

    def spy_tenant_factory(tenant_id: str) -> object:
        seen_tenant_ids.append(tenant_id)
        from _lib.wiring import build_tenant

        return build_tenant(tenant_id)

    status, _ = run_dispatch(
        app_check_token="ignored",
        authorization_header=None,
        raw_body=_BODY,
        verifier=NoopAppCheckVerifier(),
        auth_verifier=NoopAuthVerifier(),
        tenant_factory=spy_tenant_factory,  # type: ignore[arg-type]
    )

    assert status == 200
    assert seen_tenant_ids == ["t-1"]


def test_bad_body_returns_400() -> None:
    """An empty prompt fails validation before the gateway runs."""
    status, body = run_dispatch(
        app_check_token="ignored",
        authorization_header="Bearer ignored",
        raw_body=json.dumps({"prompt": "  "}).encode(),
        verifier=NoopAppCheckVerifier(),
        auth_verifier=NoopAuthVerifier(),
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
        authorization_header="Bearer ignored",
        raw_body=_BODY,
        verifier=NoopAppCheckVerifier(),
        auth_verifier=NoopAuthVerifier(),
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
