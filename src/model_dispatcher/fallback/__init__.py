"""Chain-of-Responsibility fallback handling."""

from __future__ import annotations

from .chain import FallbackChain
from .conditions import is_fallback_worthy, is_retryable, is_terminal
from .handlers import (
    AttemptRecord,
    CredentialHandler,
    FallbackHandler,
    HandlerOutcome,
    InvocationContext,
    ModelInvocationHandler,
    PerimeterHandler,
    QuotaHandler,
    RateLimitHandler,
    RetryHandler,
)

__all__ = [
    "FallbackChain",
    "FallbackHandler",
    "HandlerOutcome",
    "InvocationContext",
    "AttemptRecord",
    "PerimeterHandler",
    "CredentialHandler",
    "QuotaHandler",
    "ModelInvocationHandler",
    "RateLimitHandler",
    "RetryHandler",
    "is_retryable",
    "is_fallback_worthy",
    "is_terminal",
]
