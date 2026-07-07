"""The public facade: :class:`ModelGateway`.

A single entry point that hides the whole pipeline — perimeter, credentials,
triage, routing, fallback chain, agent loop, and quota commit — behind two
methods (:meth:`dispatch` / :meth:`adispatch`). Applications construct one
gateway at startup and call it for every request; nothing else in this package
is part of the day-to-day API surface.
"""

from __future__ import annotations

from .config import GatewaySettings
from .onboarding.flow import OnboardingResolver
from .orchestration.loop import AgentLoop
from .orchestration.result import RunResult
from .orchestration.tools import ToolRegistry
from .providers.registry import ProviderRegistry
from .quota.manager import QuotaManager
from .quota.tenant import TenantContext
from .routing.router import ModelRouter
from .routing.triage import TaskTriage
from .security.perimeter import PerimeterValidator
from .types import CompletionRequest

__all__ = ["ModelGateway"]


class ModelGateway:
    """Resilient AI model gateway/router — the library's single public entry point.

    Collaborators are injected so the gateway stays a thin orchestrator: it owns
    the *sequence* of steps, not their implementations.
    """

    def __init__(
        self,
        settings: GatewaySettings,
        *,
        providers: ProviderRegistry,
        perimeter: PerimeterValidator,
        triage: TaskTriage,
        router: ModelRouter,
        quota: QuotaManager,
        onboarding: OnboardingResolver,
        agent_loop: AgentLoop,
    ) -> None:
        self._settings = settings
        self._providers = providers
        self._perimeter = perimeter
        self._triage = triage
        self._router = router
        self._quota = quota
        self._onboarding = onboarding
        self._agent_loop = agent_loop

    def dispatch(
        self,
        request: CompletionRequest,
        tenant: TenantContext,
        *,
        tools: ToolRegistry | None = None,
    ) -> RunResult:
        """Route, run, and return the outcome for ``request`` (synchronous).

        Algorithm:
            1. ``PerimeterValidator.validate`` — reject unauthorised/malformed
               requests at the edge (may raise :class:`PerimeterViolation`).
            2. ``TaskTriage.classify`` — assign a complexity verdict.
            3. ``ModelRouter.route`` — produce the cheapest-first candidate list.
            4. Build the fallback chain (perimeter, credential, quota, invocation,
               rate-limit, retry links).
            5. ``AgentLoop.run`` — drive the tool-calling loop, dispatching every
               turn through the chain so fallback/quota/security apply per turn.
            6. ``QuotaManager.commit`` — reconcile reserved vs. actual usage.

        Raises:
            QuotaExceededError: When the zero-setup capacity is spent; carries the
                Stage-2 ``trigger_key_wizard`` handoff payload.
            AllProvidersExhausted: When every routed candidate fails.
            PerimeterViolation | AuthenticationError: On edge rejection.
        """
        raise NotImplementedError

    async def adispatch(
        self,
        request: CompletionRequest,
        tenant: TenantContext,
        *,
        tools: ToolRegistry | None = None,
    ) -> RunResult:
        """Async counterpart of :meth:`dispatch` (the native core path)."""
        raise NotImplementedError
