"""Tests for the Firebase Auth ID-token verifier's testable-without-firebase seams.

The bearer-token parsing helper, the no-op dev strategy, and the env-var switch
are all exercisable without ``firebase-admin`` installed (mirrors
``test_firebase_app.py``'s scope-without-the-dependency approach). Actual token
verification (``FirebaseAuthVerifier.verify`` with a real token) requires a
live Firebase project and is out of scope for unit tests, same as App Check.
"""

from __future__ import annotations

import pytest
from _lib.auth import (
    AuthClaims,
    AuthError,
    FirebaseAuthVerifier,
    NoopAuthVerifier,
    _extract_bearer_token,
    build_auth_verifier,
)


def test_extract_bearer_token_parses_the_standard_form() -> None:
    """A well-formed ``Bearer <token>`` header yields the bare token."""
    assert _extract_bearer_token("Bearer abc123") == "abc123"


def test_extract_bearer_token_is_case_insensitive_on_scheme() -> None:
    """The ``Bearer`` scheme name is matched case-insensitively per RFC 6750."""
    assert _extract_bearer_token("bearer abc123") == "abc123"


def test_extract_bearer_token_rejects_missing_header() -> None:
    """A ``None`` header fails closed rather than silently returning no token."""
    with pytest.raises(AuthError):
        _extract_bearer_token(None)


def test_extract_bearer_token_rejects_non_bearer_scheme() -> None:
    """A non-Bearer credential (e.g. Basic auth) is rejected, not ignored."""
    with pytest.raises(AuthError):
        _extract_bearer_token("Basic dXNlcjpwYXNz")


def test_extract_bearer_token_rejects_bearer_with_no_token() -> None:
    """The literal string "Bearer" with nothing after it is malformed, not empty-ok."""
    with pytest.raises(AuthError):
        _extract_bearer_token("Bearer")


def test_noop_verifier_never_verifies_and_returns_no_uid() -> None:
    """The dev strategy always succeeds but never yields an authoritative uid.

    ``uid is None`` is the signal callers use to fall back to a client-declared
    tenant id — this is the contract :mod:`_lib.pipeline` depends on.
    """
    claims = NoopAuthVerifier().verify(None)
    assert isinstance(claims, AuthClaims)
    assert claims.uid is None

    # Even a well-formed header is ignored — the strategy performs no checks.
    claims_with_header = NoopAuthVerifier().verify("Bearer whatever")
    assert claims_with_header.uid is None


def test_firebase_verifier_fails_closed_without_a_token() -> None:
    """A missing/malformed header is rejected before any Firebase call is made."""
    with pytest.raises(AuthError):
        FirebaseAuthVerifier().verify(None)


def test_build_auth_verifier_defaults_to_enforce(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Omitting MD_AUTH_MODE selects the real (fail-closed) verifier."""
    monkeypatch.delenv("MD_AUTH_MODE", raising=False)
    assert isinstance(build_auth_verifier(), FirebaseAuthVerifier)


def test_build_auth_verifier_disabled_selects_noop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MD_AUTH_MODE=disabled selects the dev/no-op verifier."""
    monkeypatch.setenv("MD_AUTH_MODE", "disabled")
    assert isinstance(build_auth_verifier(), NoopAuthVerifier)
