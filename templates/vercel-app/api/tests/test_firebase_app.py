"""Tests for the shared Firebase bootstrap's credential-parsing helper.

Used by both the App Check verifier (:mod:`_lib.appcheck`) and the Auth
verifier (:mod:`_lib.auth`).
"""

from __future__ import annotations

import base64
import json

import pytest
from _lib.firebase_app import parse_service_account_json


def test_parses_raw_json() -> None:
    """A plain JSON service-account body round-trips unchanged."""
    payload = {"type": "service_account", "project_id": "demo"}
    assert parse_service_account_json(json.dumps(payload)) == payload


def test_parses_base64_encoded_json() -> None:
    """A base64-wrapped body (the Vercel-friendly form) decodes to the same dict."""
    payload = {"type": "service_account", "project_id": "demo"}
    encoded = base64.b64encode(json.dumps(payload).encode()).decode()
    assert parse_service_account_json(encoded) == payload


def test_tolerates_surrounding_whitespace() -> None:
    """Leading/trailing whitespace (common when pasted into a dashboard) is stripped."""
    payload = {"type": "service_account", "project_id": "demo"}
    assert parse_service_account_json(f"  {json.dumps(payload)}\n") == payload


def test_neither_json_nor_base64_raises() -> None:
    """Garbage input fails loudly rather than silently producing an empty app.

    Every realistic failure here — a JSON parse error, invalid base64 padding,
    or a UTF-8 decode error on the decoded bytes — is a :class:`ValueError`.
    """
    with pytest.raises(ValueError):
        parse_service_account_json("not json and not base64 either !!")
