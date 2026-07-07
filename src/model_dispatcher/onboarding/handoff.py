"""The Stage-2 GUI handoff contract.

When the zero-setup capacity is spent, the library must hand control back to the
front end with a *structured* instruction to launch its key wizard — not an
opaque 500. :class:`HandoffResponse` is that contract, and :meth:`to_payload`
produces exactly the JSON the requirements specify::

    {"error": "quota_exceeded", "provider": "openai", "action": "trigger_key_wizard"}
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ..types import JSONValue

__all__ = ["HandoffAction", "HandoffResponse", "KeyWizardHandoff"]


class HandoffAction(StrEnum):
    """The action the front end should take on receiving a handoff."""

    TRIGGER_KEY_WIZARD = "trigger_key_wizard"
    UPGRADE_PLAN = "upgrade_plan"
    RETRY_LATER = "retry_later"


@dataclass(frozen=True, slots=True)
class HandoffResponse:
    """Structured, serialisable instruction returned to the consuming app.

    Attributes:
        error: Machine-readable error code (e.g. ``"quota_exceeded"``).
        provider: The provider whose limit was hit, so the wizard can pre-select.
        action: What the client UI should do next.
        http_status: Status a web layer should surface — ``402`` for a
            budget/upgrade wall, ``429`` for a rolling rate window.
        detail: Optional human-readable explanation for display/logging.
    """

    error: str
    provider: str
    action: HandoffAction
    http_status: int
    detail: str | None = None

    def to_payload(self) -> dict[str, JSONValue]:
        """Return the exact JSON body the front end consumes.

        Example::

            {"error": "quota_exceeded", "provider": "openai",
             "action": "trigger_key_wizard"}
        """
        raise NotImplementedError


class KeyWizardHandoff:
    """Factory that builds :class:`HandoffResponse` objects for quota breaches."""

    def build(
        self,
        provider: str,
        *,
        reason: str = "quota_exceeded",
        rate_window: bool = False,
    ) -> HandoffResponse:
        """Construct the handoff for a breach on ``provider``.

        Args:
            provider: Provider whose limit was reached.
            reason: Machine-readable error code embedded in the payload.
            rate_window: When ``True`` the breach is a short rolling window
                (``http_status`` 429); otherwise it is a budget/upgrade wall
                (``http_status`` 402).

        Returns:
            A :class:`HandoffResponse` carrying the ``trigger_key_wizard`` action.
        """
        raise NotImplementedError
