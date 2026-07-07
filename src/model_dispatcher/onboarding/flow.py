"""Two-stage onboarding resolution.

The onboarding resolver decides which stage a tenant is in and, on a quota
breach, whether to stay zero-setup (fall back to a cheaper free candidate) or
escalate to the guided key-wizard handoff.
"""

from __future__ import annotations

from enum import StrEnum

from ..quota.tenant import TenantContext
from .handoff import HandoffResponse, KeyWizardHandoff

__all__ = ["OnboardingStage", "OnboardingResolver"]


class OnboardingStage(StrEnum):
    """Which onboarding stage applies to the current tenant.

    Members:
        ZERO_SETUP: The tenant rides the free tier / shared global key with no
            credential of their own (Stage 1).
        GUIDED_HANDOFF: The tenant must supply their own key to continue; the
            library returns a structured wizard handoff (Stage 2).
    """

    ZERO_SETUP = "zero_setup"
    GUIDED_HANDOFF = "guided_handoff"


class OnboardingResolver:
    """Determines the onboarding stage and builds Stage-2 handoffs."""

    def __init__(self, handoff_factory: KeyWizardHandoff) -> None:
        self._handoff = handoff_factory

    def stage(self, tenant: TenantContext) -> OnboardingStage:
        """Return the stage that applies to ``tenant``.

        A tenant riding the shared global key / free tier is ``ZERO_SETUP`` until
        that shared capacity is exhausted; a tenant with their own credential is
        never forced into a handoff by quota alone.
        """
        raise NotImplementedError

    def escalate(
        self, tenant: TenantContext, provider: str, *, rate_window: bool
    ) -> HandoffResponse:
        """Build the Stage-2 handoff for a tenant that has hit its wall.

        Delegates payload construction to :class:`KeyWizardHandoff`; the caller
        wraps the result in :class:`QuotaExceededError` to unwind the pipeline.
        """
        raise NotImplementedError
