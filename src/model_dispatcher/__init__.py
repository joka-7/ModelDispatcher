"""ModelDispatcher — a resilient AI Model Gateway/Router.

Public API surface. Import the facade and the value types from here; the
subpackages (``providers``, ``routing``, ``fallback``, ``orchestration``,
``quota``, ``security``, ``onboarding``) expose the extension points.

Example:
    >>> from model_dispatcher import ModelGateway, CompletionRequest  # doctest: +SKIP

Routing, fallback, quota, the agent loop, and onboarding all run end-to-end
against real provider adapters (OpenAI/Anthropic/Gemini/Groq/OpenRouter/
Cerebras/Mistral) and a keyless :class:`~model_dispatcher.providers.MockProvider`
for offline use.
"""

from __future__ import annotations

from .config import GatewaySettings, QuotaDefaults, RoutingPolicy, SecuritySettings
from .exceptions import (
    AllProvidersExhausted,
    AuthenticationError,
    ModelDispatcherError,
    PerimeterViolation,
    QuotaExceededError,
    RateLimitError,
    ToolExecutionError,
)
from .gateway import ModelGateway
from .onboarding import HandoffResponse, KeyWizardHandoff, OnboardingStage
from .orchestration import RunResult, StopReason, Tool, ToolRegistry
from .providers import (
    AnthropicProvider,
    MockProvider,
    ModelProvider,
    OpenAIProvider,
    ProviderRegistry,
)
from .quota import InMemoryQuotaStore, QuotaManager, TenantContext, TenantQuota
from .types import (
    CompletionRequest,
    CompletionResponse,
    ErrorClass,
    Message,
    ModelTier,
    ProviderCapability,
    Role,
    TaskComplexity,
    TenantId,
    ToolCall,
    ToolResult,
    ToolSpec,
    Usage,
)

__version__ = "0.3.0"

__all__ = [
    "__version__",
    # Facade + config
    "ModelGateway",
    "GatewaySettings",
    "RoutingPolicy",
    "SecuritySettings",
    "QuotaDefaults",
    # Core value types
    "CompletionRequest",
    "CompletionResponse",
    "Message",
    "Role",
    "ModelTier",
    "TaskComplexity",
    "ErrorClass",
    "ProviderCapability",
    "TenantId",
    "ToolSpec",
    "ToolCall",
    "ToolResult",
    "Usage",
    # Orchestration
    "RunResult",
    "StopReason",
    "Tool",
    "ToolRegistry",
    # Providers & registry
    "ModelProvider",
    "ProviderRegistry",
    "MockProvider",
    "OpenAIProvider",
    "AnthropicProvider",
    # Quota & tenancy
    "QuotaManager",
    "InMemoryQuotaStore",
    "TenantContext",
    "TenantQuota",
    # Onboarding
    "OnboardingStage",
    "KeyWizardHandoff",
    "HandoffResponse",
    # Exceptions
    "ModelDispatcherError",
    "PerimeterViolation",
    "AuthenticationError",
    "RateLimitError",
    "QuotaExceededError",
    "AllProvidersExhausted",
    "ToolExecutionError",
]
