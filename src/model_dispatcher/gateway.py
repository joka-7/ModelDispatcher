"""The public facade: :class:`ModelGateway`.

A single entry point that hides the whole pipeline — perimeter, credentials,
triage, routing, fallback chain, agent loop, and quota commit — behind two
methods (:meth:`dispatch` / :meth:`adispatch`). Applications construct one
gateway at startup (usually via :meth:`create`) and call it for every request;
nothing else in this package is part of the day-to-day API surface.
"""

from __future__ import annotations

from .config import GatewaySettings
from .fallback.chain import FallbackChain
from .fallback.handlers import (
    CredentialHandler,
    ModelInvocationHandler,
    PerimeterHandler,
    QuotaHandler,
)
from .onboarding.flow import OnboardingResolver
from .onboarding.handoff import KeyWizardHandoff
from .orchestration.loop import AgentLoop
from .orchestration.result import RunResult
from .orchestration.state import ConversationState
from .orchestration.tools import ToolRegistry
from .providers.base import ModelProvider
from .providers.registry import ProviderRegistry
from .quota.manager import QuotaManager
from .quota.store import InMemoryQuotaStore, QuotaStore
from .quota.tenant import TenantContext
from .routing.router import ModelRouter
from .routing.triage import ComplexityScorer, TaskTriage
from .security.credentials import CredentialResolver
from .security.perimeter import PerimeterValidator
from .types import CompletionRequest

__all__ = ["ModelGateway"]


class ModelGateway:
    """Resilient AI model gateway/router — the library's single public entry point.

    Collaborators are injected so the gateway stays a thin orchestrator: it owns
    the *sequence* of steps, not their implementations. Use :meth:`create` for the
    common wiring, or the constructor directly for full control in tests.
    """

    def __init__(
        self,
        settings: GatewaySettings,
        *,
        providers: ProviderRegistry,
        perimeter: PerimeterValidator,
        credentials: CredentialResolver,
        triage: TaskTriage,
        router: ModelRouter,
        quota: QuotaManager,
        onboarding: OnboardingResolver,
        agent_loop: AgentLoop,
    ) -> None:
        self._settings = settings
        self._providers = providers
        self._perimeter = perimeter
        self._credentials = credentials
        self._triage = triage
        self._router = router
        self._quota = quota
        self._onboarding = onboarding
        self._agent_loop = agent_loop

    @classmethod
    def create(
        cls,
        providers: ProviderRegistry,
        *,
        settings: GatewaySettings | None = None,
        quota_store: QuotaStore | None = None,
        scorer: ComplexityScorer | None = None,
    ) -> ModelGateway:
        """Assemble a gateway with the default collaborator wiring.

        Args:
            providers: Registry of model provider strategies (must be non-empty).
            settings: Configuration bundle; defaults to :class:`GatewaySettings`.
            quota_store: Counter backend; defaults to :class:`InMemoryQuotaStore`.
            scorer: Optional custom triage strategy.
        """
        settings = settings or GatewaySettings()
        quota = QuotaManager(quota_store or InMemoryQuotaStore())
        credentials = CredentialResolver()
        return cls(
            settings,
            providers=providers,
            perimeter=PerimeterValidator(settings.security, credentials),
            credentials=credentials,
            triage=TaskTriage(scorer),
            router=ModelRouter(providers, settings.routing),
            quota=quota,
            onboarding=OnboardingResolver(KeyWizardHandoff()),
            agent_loop=AgentLoop(settings.max_iterations),
        )

    @property
    def providers(self) -> ProviderRegistry:
        """Return the provider registry backing this gateway."""
        return self._providers

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
            4. Build the fallback chain (perimeter, credential, quota, invocation).
            5. ``AgentLoop.run`` — drive the tool-calling loop, dispatching every
               turn through the chain so fallback/quota/security apply per turn.

        Raises:
            QuotaExceededError: When the zero-setup capacity is spent; carries the
                Stage-2 ``trigger_key_wizard`` handoff payload.
            AllProvidersExhausted: When every routed candidate fails.
            PerimeterViolation | AuthenticationError: On edge rejection.
        """
        state, registry, candidates = self._prepare(request, tenant, tools)
        chain = self._build_chain()
        return self._agent_loop.run(state, tenant, registry, chain, candidates)

    async def adispatch(
        self,
        request: CompletionRequest,
        tenant: TenantContext,
        *,
        tools: ToolRegistry | None = None,
    ) -> RunResult:
        """Async counterpart of :meth:`dispatch` (the native core path)."""
        state, registry, candidates = self._prepare(request, tenant, tools)
        chain = self._build_chain()
        return await self._agent_loop.arun(state, tenant, registry, chain, candidates)

    # -- helpers ---------------------------------------------------------- #

    def _prepare(
        self,
        request: CompletionRequest,
        tenant: TenantContext,
        tools: ToolRegistry | None,
    ) -> tuple[ConversationState, ToolRegistry, list[ModelProvider]]:
        """Validate, triage, route, and build the initial run state."""
        self._perimeter.validate(request, tenant)
        complexity = self._triage.classify(request)
        candidates = self._router.route(request, complexity)

        registry = tools or ToolRegistry()
        effective_tools = registry.specs() if tools is not None else request.tools
        state = ConversationState(
            tenant=tenant.tenant_id,
            messages=list(request.messages),
            tools=effective_tools,
        )
        return state, registry, candidates

    def _build_chain(self) -> FallbackChain:
        """Compose the per-dispatch fallback chain of responsibility."""
        return FallbackChain.build(
            [
                PerimeterHandler(self._perimeter),
                CredentialHandler(self._credentials),
                QuotaHandler(self._quota, self._onboarding),
                ModelInvocationHandler(
                    self._quota, max_attempts=self._settings.retry_max_attempts
                ),
            ]
        )
