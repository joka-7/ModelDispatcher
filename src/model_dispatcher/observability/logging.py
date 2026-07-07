"""Structured, redaction-aware logging.

A thin wrapper over the stdlib logger that routes every structured field through
:class:`SecretRedactor` before emission, so instrumentation added anywhere in the
pipeline cannot accidentally leak credentials or PII.
"""

from __future__ import annotations

import logging

from ..security.redaction import SecretRedactor
from ..types import JSONValue

__all__ = ["StructuredLogger"]


class StructuredLogger:
    """Emits structured log events with automatic secret redaction."""

    def __init__(self, name: str, redactor: SecretRedactor | None = None) -> None:
        self._logger = logging.getLogger(name)
        self._redactor = redactor or SecretRedactor()

    def event(self, name: str, **fields: JSONValue) -> None:
        """Emit a structured event named ``name`` with redacted ``fields``."""
        safe: JSONValue = self._redactor.scrub(dict(fields))
        self._logger.info("%s %s", name, safe)
