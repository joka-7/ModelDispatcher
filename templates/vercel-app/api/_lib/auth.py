"""Firebase Auth-backed tenant identity for the Vercel perimeter (Strategy pattern).

App Check (see :mod:`_lib.appcheck`) attests the *app*; it does not identify the
*end user*, so it cannot make per-tenant quota isolation meaningful — every
caller behind a legitimate app instance could still claim any ``tenant_id`` it
liked in the request body. This module closes that gap: it verifies a Firebase
Auth ID token and derives the tenant id from its cryptographically-verified
``uid`` claim, so quota isolation is no longer just a client-supplied string.

Mirrors :mod:`_lib.appcheck`'s shape exactly (a :class:`Protocol` with a real
Firebase strategy and a no-op dev strategy, selected by an env var) — the same
pluggable-seam pattern used throughout the library (``QuotaStore``,
``MetricsSink``, ``AppCheckVerifier``).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

from _lib.firebase_app import ensure_default_app

#: HTTP header the frontend sends the ID token in: ``Authorization: Bearer <token>``.
AUTHORIZATION_HEADER = "Authorization"


class AuthError(Exception):
    """Raised when an Authorization header is missing, malformed, or invalid.

    The wrapper maps this to a ``401 unauthenticated`` response and never
    invokes the gateway, so verification failure costs no downstream work.
    """


@dataclass(frozen=True, slots=True)
class AuthClaims:
    """The subset of verified identity the wrapper cares about.

    Attributes:
        uid: The Firebase Auth user id, or ``None`` when no identity was
            cryptographically verified (only possible via
            :class:`NoopAuthVerifier`, i.e. ``MD_AUTH_MODE=disabled``). Callers
            must treat ``None`` as "no authoritative tenant id" and fall back to
            whatever the request body declares.
    """

    uid: str | None


class AuthVerifier(Protocol):
    """Strategy interface: verify a raw ``Authorization`` header into claims."""

    def verify(self, header_value: str | None) -> AuthClaims:
        """Verify ``header_value`` or raise :class:`AuthError`."""
        ...


def _extract_bearer_token(header_value: str | None) -> str:
    """Pull the token out of an ``Authorization: Bearer <token>`` header.

    Raises:
        AuthError: If the header is absent or not a ``Bearer`` credential.
    """
    if not header_value:
        raise AuthError("missing Authorization header")
    scheme, _, token = header_value.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AuthError("Authorization header must be a Bearer token")
    return token


class FirebaseAuthVerifier:
    """Production verifier backed by ``firebase_admin.auth.verify_id_token``.

    The Firebase Admin SDK is imported lazily inside :meth:`verify` so this
    module stays import-light and unit-testable without the dependency
    installed, matching :class:`_lib.appcheck.FirebaseAppCheckVerifier`.
    """

    def verify(self, header_value: str | None) -> AuthClaims:
        """Cryptographically verify a Firebase Auth ID token.

        Algorithm:
            1. Extract the bearer token; reject outright if absent/malformed
               (fail closed).
            2. Ensure the default Firebase app is initialised (idempotent,
               shared with the App Check verifier).
            3. Delegate to ``firebase_admin.auth.verify_id_token``, which checks
               the signature, audience, issuer, and expiry against Google's keys.
            4. Return the verified ``uid`` claim.

        Args:
            header_value: The raw ``Authorization`` header value.

        Returns:
            Claims carrying the verified, non-``None`` ``uid``.

        Raises:
            AuthError: If the header is missing/malformed or the token fails
                verification.
        """
        token = _extract_bearer_token(header_value)

        from firebase_admin import auth  # lazy import; see class docstring

        ensure_default_app()

        try:
            decoded = auth.verify_id_token(token)
        except Exception as exc:  # noqa: BLE001 - normalise any SDK error to ours
            raise AuthError(f"invalid ID token: {exc}") from exc

        uid = decoded.get("uid")
        if not uid:
            raise AuthError("ID token carried no uid")
        return AuthClaims(uid=str(uid))


class NoopAuthVerifier:
    """Development strategy that accepts any request without verifying identity.

    Returns ``AuthClaims(uid=None)`` unconditionally, signalling "no verified
    identity" so the caller falls back to the client-declared ``tenant_id`` —
    the same anonymous/dev behaviour the wrapper had before this module existed.
    Selected when auth is disabled (local dev, the keyless ``demo/``, and tests)
    so nothing needs a Firebase project to run. Never wire this in production —
    it performs no verification, so per-tenant quota isolation is not
    meaningful while it's active.
    """

    def verify(self, header_value: str | None) -> AuthClaims:
        """Return an unverified claim, always."""
        return AuthClaims(uid=None)


def build_auth_verifier() -> AuthVerifier:
    """Select a verifier from the environment.

    Reads ``MD_AUTH_MODE``: ``"enforce"`` (default) uses
    :class:`FirebaseAuthVerifier`; ``"disabled"`` uses :class:`NoopAuthVerifier`.
    Constructed once at module import and reused across warm serverless
    invocations, mirroring :func:`_lib.appcheck.build_verifier`.
    """
    mode = os.environ.get("MD_AUTH_MODE", "enforce").strip().lower()
    if mode == "disabled":
        return NoopAuthVerifier()
    return FirebaseAuthVerifier()
