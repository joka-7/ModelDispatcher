"""Vercel serverless entrypoint: the thin gateway wrapper (Adapter pattern).

Any file under ``/api`` becomes a Vercel Function, so this module *is* the
``POST /api/gateway`` endpoint. It is a pure I/O shell: it reads the App Check
header and request body off the socket and delegates every decision to
:func:`_lib.pipeline.run_dispatch`, which performs the guard → adapt → invoke →
map pipeline. The gateway library is installed from ``requirements.txt``
(git-pinned), so this file never changes when the library is upgraded.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler
from typing import Any

from _lib.appcheck import APP_CHECK_HEADER, build_verifier
from _lib.pipeline import run_dispatch

# Built once per warm serverless instance and reused across invocations.
_VERIFIER = build_verifier()


class handler(BaseHTTPRequestHandler):  # noqa: N801 - Vercel mandates this exact name
    """Vercel Python handler for the gateway endpoint."""

    def do_POST(self) -> None:  # noqa: N802 - name mandated by BaseHTTPRequestHandler
        """Read the request and run the dispatch pipeline."""
        length = int(self.headers.get("content-length") or 0)
        raw_body = self.rfile.read(length) if length else b"{}"
        status, body = run_dispatch(
            app_check_token=self.headers.get(APP_CHECK_HEADER),
            raw_body=raw_body,
            verifier=_VERIFIER,
        )
        self._write_json(status, body)

    def do_GET(self) -> None:  # noqa: N802 - name mandated by BaseHTTPRequestHandler
        """Reject non-POST verbs; the gateway only accepts POST."""
        self._write_json(405, {"error": "method_not_allowed"})

    def log_message(self, _format: str, *_args: Any) -> None:
        """Silence the default stderr access log (Vercel captures its own)."""

    def _write_json(self, status: int, body: dict[str, Any]) -> None:
        """Serialise ``body`` as JSON with the given status code."""
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
