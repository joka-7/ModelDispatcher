"""Shared Firebase Admin SDK bootstrap.

Both the App Check verifier (:mod:`_lib.appcheck`) and the Auth ID-token
verifier (:mod:`_lib.auth`) need exactly one initialised default Firebase app
before they can call into the Admin SDK. Centralising that bootstrap here means
whichever guard runs first pays the one-time init cost and the other is a no-op,
regardless of call order.
"""

from __future__ import annotations

import base64
import json
import os
from typing import Any


def parse_service_account_json(raw: str) -> dict[str, Any]:
    """Parse a service-account credential from raw or base64-encoded JSON.

    Vercel env vars are plain strings, so the credential can be pasted either as
    the service-account JSON verbatim or, to dodge shell/UI quoting issues, as
    its base64 encoding. Both are accepted transparently.
    """
    stripped = raw.strip()
    try:
        info: dict[str, Any] = json.loads(stripped)
    except json.JSONDecodeError:
        info = json.loads(base64.b64decode(stripped))
    return info


def ensure_default_app() -> None:
    """Initialise the default Firebase app on first use, once per process.

    Every ``firebase_admin.*`` verification call (App Check, Auth) requires a
    default app to exist. Safe to call on every invocation: a warm serverless
    instance already has the app and this is a cheap no-op after cold start.

    Algorithm:
        1. If a default app already exists, do nothing.
        2. Else, if ``FIREBASE_SERVICE_ACCOUNT_JSON`` is set, build credentials
           from it directly (accepts raw JSON or base64-encoded JSON) — this is
           the path for Vercel, which has no persistent filesystem to point a
           credentials *file* at.
        3. Else, fall back to :func:`firebase_admin.initialize_app` with no
           arguments, which resolves Application Default Credentials (e.g. a
           ``GOOGLE_APPLICATION_CREDENTIALS`` file path) — the convenient path
           for local development.
    """
    import firebase_admin

    try:
        firebase_admin.get_app()
        return
    except ValueError:
        pass

    service_account_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
    if service_account_json:
        from firebase_admin import credentials

        info = parse_service_account_json(service_account_json)
        firebase_admin.initialize_app(credentials.Certificate(info))
    else:
        firebase_admin.initialize_app()
