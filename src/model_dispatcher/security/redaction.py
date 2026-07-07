"""Secret and PII redaction for logs and metrics.

Anything that leaves the process boundary as a log line or metric label passes
through :class:`SecretRedactor` first, so API keys, bearer tokens, and obvious
PII never leak into observability sinks.
"""

from __future__ import annotations

from ..types import JSONValue

__all__ = ["SecretRedactor"]


class SecretRedactor:
    """Recursively scrubs sensitive values from structures bound for logs.

    Algorithm:
        Walks a JSON-like structure and replaces values whose *key* matches a
        sensitive-name pattern (``api_key``, ``authorization``, ``secret``, ...)
        or whose *value* matches a secret-shaped regex (long high-entropy tokens,
        ``sk-`` prefixes, bearer tokens) with a fixed ``"[REDACTED]"`` sentinel,
        leaving structure and non-sensitive values intact.
    """

    def scrub(self, value: JSONValue) -> JSONValue:
        """Return a copy of ``value`` with sensitive fields redacted."""
        raise NotImplementedError

    def scrub_text(self, text: str) -> str:
        """Return ``text`` with inline secret-shaped substrings redacted."""
        raise NotImplementedError
