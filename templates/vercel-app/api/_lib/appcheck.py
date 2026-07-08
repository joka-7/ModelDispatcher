"""Firebase App Check verification for the Vercel perimeter (Strategy pattern).

App Check cryptographically attests that a request originated from *your* genuine,
unmodified frontend app instance (via reCAPTCHA / DeviceCheck / Play Integrity),
which is the anti-abuse gate the perimeter needs before spending any compute. The
verifier is expressed as a :class:`Protocol` with two concrete strategies — a real
Firebase one and a no-op for local/dev — mirroring the library's own pluggable
seams (``QuotaStore``, ``MetricsSink``). The gateway wrapper selects one via
:func:`build_verifier` and never imports Firebase directly.

Note:
    App Check identifies the *app*, not the end user. The ``app_id`` claim gates
    abuse; per-user/tenant identity is a separate, stronger guard — see
    :mod:`_lib.auth`, which verifies a Firebase Auth ID token and derives the
    authoritative tenant id from it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

from _lib.firebase_app import ensure_default_app

#: HTTP header the frontend sends the App Check attestation token in.
APP_CHECK_HEADER = "X-Firebase-AppCheck"


class AppCheckError(Exception):
    """Raised when an App Check token is missing, malformed, or invalid.

    The wrapper maps this to a ``403 app_check_failed`` response and never invokes
    the gateway, so verification failure costs no downstream work.
    """


@dataclass(frozen=True, slots=True)
class AppCheckClaims:
    """The subset of verified App Check claims the wrapper cares about.

    Attributes:
        app_id: The Firebase application id the token was issued to.
        subject: The token ``sub`` claim (also the app id, per the App Check spec).
    """

    app_id: str
    subject: str


class AppCheckVerifier(Protocol):
    """Strategy interface: verify a raw header token into :class:`AppCheckClaims`."""

    def verify(self, token: str | None) -> AppCheckClaims:
        """Verify ``token`` or raise :class:`AppCheckError`."""
        ...


class FirebaseAppCheckVerifier:
    """Production verifier backed by ``firebase_admin.app_check.verify_token``.

    The Firebase Admin SDK is imported lazily inside :meth:`verify` so this module
    stays import-light and unit-testable without the dependency installed.
    """

    def verify(self, token: str | None) -> AppCheckClaims:
        """Cryptographically verify an App Check token.

        Algorithm:
            1. Reject an absent token outright (fail closed).
            2. Ensure the default Firebase app is initialised (idempotent; the
               SDK has no per-call verification path without one).
            3. Delegate to ``firebase_admin.app_check.verify_token``, which checks
               the signature, audience, issuer, and expiry against Google's keys.
            4. Normalise the returned claim dict into :class:`AppCheckClaims`.

        Args:
            token: The raw ``X-Firebase-AppCheck`` header value.

        Returns:
            The verified claims.

        Raises:
            AppCheckError: If the token is missing or fails verification.
        """
        if not token:
            raise AppCheckError("missing App Check token")

        from firebase_admin import app_check  # lazy import; see class docstring

        ensure_default_app()

        try:
            claims = app_check.verify_token(token)
        except Exception as exc:  # noqa: BLE001 - normalise any SDK error to ours
            raise AppCheckError(f"invalid App Check token: {exc}") from exc

        app_id = str(claims.get("app_id") or claims.get("sub") or "")
        if not app_id:
            raise AppCheckError("App Check token carried no app_id")
        return AppCheckClaims(app_id=app_id, subject=str(claims.get("sub", app_id)))


class NoopAppCheckVerifier:
    """Development strategy that accepts any request without attestation.

    Selected when App Check is disabled (local dev, the keyless ``demo/``, and
    tests) so nothing needs a Firebase project to run. Never wire this in
    production — it performs no verification.
    """

    def verify(self, token: str | None) -> AppCheckClaims:
        """Return placeholder claims without verifying anything."""
        return AppCheckClaims(app_id="dev-bypass", subject="dev-bypass")


def build_verifier() -> AppCheckVerifier:
    """Select a verifier from the environment.

    Reads ``MD_APP_CHECK_MODE``: ``"enforce"`` (default) uses
    :class:`FirebaseAppCheckVerifier`; ``"disabled"`` uses
    :class:`NoopAppCheckVerifier`. Constructed once at module import and reused
    across warm serverless invocations.
    """
    mode = os.environ.get("MD_APP_CHECK_MODE", "enforce").strip().lower()
    if mode == "disabled":
        return NoopAppCheckVerifier()
    return FirebaseAppCheckVerifier()
