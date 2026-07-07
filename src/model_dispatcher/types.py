"""Shared vocabulary for the gateway.

This module is the single source of truth for the data structures that flow
across every subsystem (providers, routing, fallback, orchestration, quota,
security, onboarding). Keeping them here — free of any behaviour — prevents
import cycles and lets each subsystem depend only on plain, hashable value
objects.

All request/response objects are immutable dataclasses so they can be shared
safely across the async agent loop without defensive copying.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Flag, IntEnum, StrEnum, auto
from typing import NewType

__all__ = [
    "TenantId",
    "JSONValue",
    "Role",
    "ModelTier",
    "TaskComplexity",
    "ErrorClass",
    "ProviderCapability",
    "Usage",
    "ToolSpec",
    "ToolCall",
    "ToolResult",
    "Message",
    "CompletionRequest",
    "CompletionResponse",
]

# --------------------------------------------------------------------------- #
# Primitive aliases
# --------------------------------------------------------------------------- #

TenantId = NewType("TenantId", str)
"""Opaque per-tenant identity used to scope quotas, credentials, and metrics."""

type JSONValue = (
    None | bool | int | float | str | list[JSONValue] | dict[str, JSONValue]
)
"""Recursive alias describing any JSON-serialisable value (PEP 695)."""


# --------------------------------------------------------------------------- #
# Enumerations
# --------------------------------------------------------------------------- #


class Role(StrEnum):
    """Conversation role of a :class:`Message`, mirroring chat-completion APIs."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ModelTier(IntEnum):
    """Cost/capability tier of a provider.

    Declared as an ``IntEnum`` so tiers are naturally orderable: routing can ask
    for "at least ``STANDARD``" with a simple ``>=`` comparison, and candidate
    lists sort cheapest-first by ascending value.
    """

    FREE = 0
    CHEAP = 1
    STANDARD = 2
    PREMIUM = 3


class TaskComplexity(IntEnum):
    """Triage verdict describing how much reasoning a request demands.

    Orderable so the router can map a complexity floor onto a minimum
    :class:`ModelTier` monotonically.
    """

    TRIVIAL = 0
    SIMPLE = 1
    MODERATE = 2
    COMPLEX = 3


class ErrorClass(StrEnum):
    """Normalised error category.

    Concrete providers translate their SDK-specific exceptions into one of these
    classes via :meth:`ModelProvider.classify_error`, so the fallback chain can
    reason about failures without knowing any vendor's exception taxonomy.
    """

    RATE_LIMIT = "rate_limit"
    QUOTA = "quota"
    AUTH = "auth"
    TRANSIENT = "transient"
    INVALID = "invalid"
    CONTENT = "content"


class ProviderCapability(Flag):
    """Bitwise-combinable feature flags advertised by a provider.

    Used by routing to filter candidates (e.g. a request carrying tools must map
    only to providers whose capabilities include ``TOOLS``).
    """

    NONE = 0
    TOOLS = auto()
    STREAMING = auto()
    VISION = auto()
    JSON_MODE = auto()


# --------------------------------------------------------------------------- #
# Value objects
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class Usage:
    """Token accounting for a single model call."""

    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        """Return the combined prompt and completion token count."""
        return self.prompt_tokens + self.completion_tokens

    def __add__(self, other: Usage) -> Usage:
        """Accumulate two usage records (used to total a multi-step run)."""
        return Usage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
        )


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """Declaration of a callable tool exposed to the model.

    ``parameters`` is a JSON Schema object describing the tool's arguments,
    matching the function-calling contract used by the major providers.
    """

    name: str
    description: str
    parameters: dict[str, JSONValue]


@dataclass(frozen=True, slots=True)
class ToolCall:
    """A model's request to invoke a tool, decoded from a completion."""

    id: str
    name: str
    arguments: dict[str, JSONValue]


@dataclass(frozen=True, slots=True)
class ToolResult:
    """The outcome of executing a :class:`ToolCall`, fed back to the model."""

    call_id: str
    content: str
    is_error: bool = False


@dataclass(frozen=True, slots=True)
class Message:
    """A single turn in a conversation.

    A message carries at most one of ``tool_calls`` (assistant requesting tools)
    or ``tool_result`` (a tool's reply); ``content`` holds natural-language text.
    """

    role: Role
    content: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    tool_result: ToolResult | None = None


@dataclass(frozen=True, slots=True)
class CompletionRequest:
    """Everything a provider needs to produce one completion.

    Attributes:
        messages: Ordered conversation history to condition the model on.
        tenant: Identity used for quota accounting and credential resolution.
        tools: Tools the model may call this turn; empty disables tool use.
        tier_hint: Optional caller override nudging routing toward a tier.
        max_tokens: Upper bound on generated tokens, if the caller caps output.
        temperature: Sampling temperature; ``None`` defers to provider default.
        metadata: Free-form passthrough for tracing/routing extensions.
    """

    messages: tuple[Message, ...]
    tenant: TenantId
    tools: tuple[ToolSpec, ...] = ()
    tier_hint: ModelTier | None = None
    max_tokens: int | None = None
    temperature: float | None = None
    metadata: dict[str, JSONValue] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CompletionResponse:
    """A provider's answer for one :class:`CompletionRequest`.

    Attributes:
        message: The assistant message (text and/or tool calls).
        usage: Token accounting reported (or estimated) for the call.
        provider_name: Name of the provider that served the request.
        tier: Tier of the serving provider (for cost attribution).
        raw: Optional vendor-native payload for debugging/passthrough.
    """

    message: Message
    usage: Usage
    provider_name: str
    tier: ModelTier
    raw: dict[str, JSONValue] | None = None
