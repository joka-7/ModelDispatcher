"""Centralised failure-classification predicates for the fallback chain.

Handlers should never inspect vendor exceptions directly. Instead they ask the
predicates here — expressed purely in terms of the normalised
:class:`ErrorClass` — whether a failure warrants a retry, a fallback to the next
candidate, or immediate propagation. Keeping this logic in one place guarantees
every handler agrees on what "retryable" means.
"""

from __future__ import annotations

from ..types import ErrorClass

__all__ = ["is_retryable", "is_fallback_worthy", "is_terminal"]


def is_retryable(error_class: ErrorClass) -> bool:
    """Return ``True`` if the same provider should be retried after backoff.

    Only transient failures (network blips, ``503``-style hiccups) qualify.
    """
    return error_class is ErrorClass.TRANSIENT


def is_fallback_worthy(error_class: ErrorClass) -> bool:
    """Return ``True`` if the request should escalate to the next candidate.

    Rate limits and provider-side quota exhaustion qualify: the model is healthy
    but unavailable *to us right now*, so a different provider may succeed.
    """
    return error_class in (ErrorClass.RATE_LIMIT, ErrorClass.QUOTA)


def is_terminal(error_class: ErrorClass) -> bool:
    """Return ``True`` if the failure should propagate without further attempts.

    Authentication, invalid-request, and content-policy failures are the caller's
    problem; retrying or falling back cannot help.
    """
    return error_class in (
        ErrorClass.AUTH,
        ErrorClass.INVALID,
        ErrorClass.CONTENT,
    )
