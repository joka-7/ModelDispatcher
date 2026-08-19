"""Extracting a vendor-supplied "retry after" hint from a rate-limit failure.

Blind exponential backoff wastes time either way: too short and you hammer a
still-rate-limited endpoint for nothing, too long and you wait past a limit
that already cleared. Providers that actually tell you how long to wait
(Anthropic/Groq embed it in the error message text — "try again in
48m55.872s"; a well-behaved HTTP API sends a standard ``Retry-After``
response header) let the fallback chain wait *exactly* as long as needed
instead. This is a generic, provider-agnostic best-effort extraction — no
per-vendor code needed, since every provider's exception is checked the same
way (see :meth:`~.base.ModelProvider.retry_after_seconds`, which every
provider inherits unless it overrides it).
"""

from __future__ import annotations

import re

__all__ = ["parse_retry_after_hint", "extract_retry_after_seconds"]

# "Please try again in 48m55.872s" / "Please try again in 1h2m47.904s"
# (Anthropic/Groq style — hours and minutes are both optional).
_DURATION_PATTERN = re.compile(
    r"try again in\s+(?:(\d+)h\s*)?(?:(\d+)m\s*)?([\d.]+)s", re.IGNORECASE
)
# "retry after 30" (plain seconds).
_PLAIN_SECONDS_PATTERN = re.compile(r"retry.{0,10}after\s+(\d+)", re.IGNORECASE)


def parse_retry_after_hint(message: str) -> float | None:
    """Extract a wait duration (seconds) from a vendor error *message*.

    Returns ``None`` when no recognised hint is present — callers should fall
    back to their own backoff schedule in that case, not treat this as an
    error.
    """
    match = _DURATION_PATTERN.search(message)
    if match:
        total = (
            float(match.group(1) or 0) * 3600
            + float(match.group(2) or 0) * 60
            + float(match.group(3) or 0)
        )
        if total > 0:
            return total

    match = _PLAIN_SECONDS_PATTERN.search(message)
    if match:
        return float(match.group(1))

    return None


def extract_retry_after_seconds(exc: Exception) -> float | None:
    """Best-effort "how long until this provider will accept another call".

    Tries the standard HTTP ``Retry-After`` response header first (duck-typed
    via ``exc.response.headers`` — present on every major vendor SDK's
    HTTP-backed exceptions without importing any of them here), then falls
    back to parsing the hint out of the exception's own message text. Only
    the simple numeric-seconds form of ``Retry-After`` is handled — an
    HTTP-date value is rare for rate-limit responses and is treated the same
    as no hint at all, not an error.

    Returns ``None`` on any failure to extract a hint (missing response
    object, missing header, non-numeric value, no message-text match) —
    always safe to call on an arbitrary exception.
    """
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if headers is not None:
        raw = headers.get("retry-after") or headers.get("Retry-After")
        if raw is not None:
            try:
                return float(raw)
            except (TypeError, ValueError):
                pass  # An HTTP-date value, or otherwise unparseable — fall through.

    return parse_retry_after_hint(str(exc))
