"""HTTP-aware exception hierarchy for the gateway.

Every error the library raises is a subclass of :class:`ModelDispatcherError`
and carries the ``http_status`` a web perimeter should surface plus a
``to_payload()`` method producing a stable JSON body. This lets a consuming web
app translate any failure into an HTTP response with a single ``except`` clause,
and it is the mechanism behind the Stage-2 onboarding handoff: one code path
(:class:`QuotaExceededError`) produces the ``trigger_key_wizard`` contract
regardless of where in the pipeline the quota breach was detected.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .types import JSONValue

if TYPE_CHECKING:
    from .onboarding.handoff import HandoffResponse

__all__ = [
    "ModelDispatcherError",
    "PerimeterViolation",
    "AuthenticationError",
    "RateLimitError",
    "QuotaExceededError",
    "AllProvidersExhausted",
    "ToolExecutionError",
]


class ModelDispatcherError(Exception):
    """Base class for all errors raised by the gateway.

    Attributes:
        http_status: The HTTP status a proxy should map this error to.
        message: Human-readable description (also the ``str`` form).
    """

    http_status: int = 500

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def to_payload(self) -> dict[str, JSONValue]:
        """Return the JSON body a web layer should serialise for this error.

        Subclasses override to enrich the payload; the base form exposes a stable
        ``error``/``detail`` envelope.
        """
        raise NotImplementedError


class PerimeterViolation(ModelDispatcherError):
    """Inbound request rejected by :class:`PerimeterValidator` (auth/size/allowlist)."""

    http_status = 403


class AuthenticationError(ModelDispatcherError):
    """No usable credential could be resolved for the tenant/provider."""

    http_status = 401


class RateLimitError(ModelDispatcherError):
    """A provider signalled a rate limit.

    Primarily an *internal* signal: the fallback chain intercepts it to escalate
    to the next candidate rather than surfacing it to the caller.
    """

    http_status = 429


class QuotaExceededError(ModelDispatcherError):
    """A tenant exceeded its token/budget quota and must supply their own key.

    This is the terminal Stage-2 onboarding error. It wraps the structured
    :class:`~model_dispatcher.onboarding.handoff.HandoffResponse` that instructs
    the front end to launch its key wizard, and its ``http_status`` is chosen by
    the handoff (``402`` for budget/upgrade, ``429`` for a rate window).
    """

    def __init__(self, handoff: HandoffResponse) -> None:
        super().__init__(
            f"quota exceeded for provider {handoff.provider!r}; "
            f"user credential required"
        )
        self.handoff = handoff
        self.http_status = handoff.http_status

    def to_payload(self) -> dict[str, JSONValue]:
        """Return the ``trigger_key_wizard`` handoff contract.

        Yields, for example::

            {"error": "quota_exceeded", "provider": "openai",
             "action": "trigger_key_wizard"}
        """
        raise NotImplementedError


class AllProvidersExhausted(ModelDispatcherError):
    """Every routed candidate failed; the fallback chain has nothing left to try."""

    http_status = 503


class ToolExecutionError(ModelDispatcherError):
    """A tool invoked by the agent loop raised.

    Carries the offending ``tool_name`` so the loop can decide whether to feed
    the error back to the model or abort the run.
    """

    def __init__(self, tool_name: str, message: str) -> None:
        super().__init__(message)
        self.tool_name = tool_name
