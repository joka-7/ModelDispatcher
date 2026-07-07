"""Secret and PII redaction for logs and metrics.

Anything that leaves the process boundary as a log line or metric label passes
through :class:`SecretRedactor` first, so API keys, bearer tokens, and obvious
PII never leak into observability sinks.
"""

from __future__ import annotations

import re

from ..types import JSONValue

__all__ = ["SecretRedactor"]

_REDACTED = "[REDACTED]"

# Field names whose *values* are always sensitive regardless of content.
_SENSITIVE_KEYS = re.compile(
    r"(api[_-]?key|authorization|auth|secret|token|password|passwd|"
    r"bearer|credential|private[_-]?key)",
    re.IGNORECASE,
)

# Value shapes that look like secrets even under an innocuous key.
_SECRET_VALUE = re.compile(
    r"(sk-[A-Za-z0-9]{16,}"  # OpenAI-style keys
    r"|Bearer\s+[A-Za-z0-9._\-]{16,}"  # bearer tokens
    r"|[A-Za-z0-9_\-]{32,})"  # long high-entropy blobs
)


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
        if isinstance(value, dict):
            scrubbed: dict[str, JSONValue] = {}
            for key, item in value.items():
                if _SENSITIVE_KEYS.search(key):
                    scrubbed[key] = _REDACTED
                else:
                    scrubbed[key] = self.scrub(item)
            return scrubbed
        if isinstance(value, list):
            return [self.scrub(item) for item in value]
        if isinstance(value, str):
            return self.scrub_text(value)
        return value

    def scrub_text(self, text: str) -> str:
        """Return ``text`` with inline secret-shaped substrings redacted."""
        return _SECRET_VALUE.sub(_REDACTED, text)
