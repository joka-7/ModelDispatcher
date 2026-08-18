"""In-memory mock provider for tests and the zero-dependency demo.

``MockProvider`` implements the full :class:`ModelProvider` strategy without any
network or credentials, so the whole gateway — routing, fallback, quota, the
agent loop, onboarding — can be exercised deterministically. It supports three
things real adapters cannot offer a test:

* **Scripted replies** — a queue of assistant messages (optionally containing
  tool calls) returned turn by turn, to drive the agent loop.
* **Failure injection** — raise a chosen :class:`ErrorClass` a fixed number of
  times before succeeding, to drive retry and fallback.
* **Key-use recording** — every ``api_key`` a caller passed to :meth:`complete`
  /:meth:`acomplete` is appended to :attr:`received_api_keys`, so tests can
  assert *which* credential was actually used per attempt (e.g. to verify
  same-provider key rotation) without needing a real HTTP mock.
"""

from __future__ import annotations

import math
from collections import deque
from typing import override

from ..types import (
    CompletionRequest,
    CompletionResponse,
    ErrorClass,
    Message,
    ModelTier,
    ProviderCapability,
    Role,
    Usage,
)
from .base import ModelProvider

__all__ = ["MockError", "MockProvider"]


class MockError(Exception):
    """Synthetic provider error carrying the :class:`ErrorClass` to simulate."""

    def __init__(self, error_class: ErrorClass) -> None:
        super().__init__(f"mock {error_class.value} error")
        self.error_class = error_class


class MockProvider(ModelProvider):
    """A deterministic, keyless :class:`ModelProvider` for tests and demos."""

    def __init__(
        self,
        name: str = "mock",
        *,
        tier: ModelTier = ModelTier.FREE,
        capabilities: ProviderCapability = ProviderCapability.TOOLS,
        reply: str = "This is a mock response.",
        scripted: list[Message] | None = None,
        fail_times: int = 0,
        fail_with: ErrorClass = ErrorClass.RATE_LIMIT,
        chars_per_token: float = 4.0,
    ) -> None:
        """Configure the mock.

        Args:
            name: Provider identity used in the registry and traces.
            tier: Cost tier this mock occupies.
            capabilities: Feature flags advertised to the router.
            reply: Default assistant text when the scripted queue is empty.
            scripted: Assistant messages returned in order, one per turn.
            fail_times: Number of leading calls that raise before succeeding.
            fail_with: Error class raised while ``fail_times`` is not exhausted.
            chars_per_token: Ratio used to synthesise a plausible token count.
        """
        self.name = name
        self.tier = tier
        self.capabilities = capabilities
        self._reply = reply
        self._scripted: deque[Message] = deque(scripted or [])
        self._remaining_failures = fail_times
        self._fail_with = fail_with
        self._chars_per_token = chars_per_token
        self.received_api_keys: list[str | None] = []

    @override
    def complete(
        self, request: CompletionRequest, *, api_key: str | None = None
    ) -> CompletionResponse:
        self.received_api_keys.append(api_key)
        if self._remaining_failures > 0:
            self._remaining_failures -= 1
            raise MockError(self._fail_with)

        message = (
            self._scripted.popleft()
            if self._scripted
            else Message(role=Role.ASSISTANT, content=self._reply)
        )
        completion_text = message.content or ""
        usage = Usage(
            prompt_tokens=self.estimate_tokens(request),
            completion_tokens=math.ceil(len(completion_text) / self._chars_per_token),
        )
        return CompletionResponse(
            message=message,
            usage=usage,
            provider_name=self.name,
            tier=self.tier,
        )

    @override
    async def acomplete(
        self, request: CompletionRequest, *, api_key: str | None = None
    ) -> CompletionResponse:
        # The mock does no real I/O, so the async path simply mirrors the sync one.
        return self.complete(request, api_key=api_key)

    @override
    def estimate_tokens(self, request: CompletionRequest) -> int:
        chars = sum(len(m.content or "") for m in request.messages)
        return max(1, math.ceil(chars / self._chars_per_token))

    @override
    def classify_error(self, exc: Exception) -> ErrorClass:
        if isinstance(exc, MockError):
            return exc.error_class
        return ErrorClass.TRANSIENT
