"""OpenAI provider strategy.

Adapter for OpenAI chat models built on the official ``openai`` SDK (an optional
extra, imported lazily inside method bodies so importing the core package never
requires the vendor dependency). Vendor exceptions are normalised into the shared
:class:`ErrorClass` taxonomy so the fallback chain never imports from ``openai``.

The ``base_url`` constructor argument is also what makes this the base class for
every *OpenAI-compatible* vendor (Groq, OpenRouter, Cerebras, Mistral — see
:mod:`.openai_compatible`): the ``openai`` SDK talks the same request/response
shape to any endpoint that implements the same chat-completions contract, so
those adapters are thin subclasses that only fix the URL, default model, and
identity rather than reimplementing translation.
"""

from __future__ import annotations

import json
from typing import Any, override

from ..quota.tokenizer import TokenCounter
from ..types import (
    CompletionRequest,
    CompletionResponse,
    ErrorClass,
    Message,
    ModelTier,
    ProviderCapability,
    Role,
    ToolCall,
    Usage,
)
from .base import ModelProvider

__all__ = ["OpenAIProvider"]

_DEFAULT_MAX_TOKENS = 4096


class OpenAIProvider(ModelProvider):
    """Adapter for OpenAI chat models."""

    def __init__(
        self,
        *,
        model: str,
        tier: ModelTier = ModelTier.STANDARD,
        api_key: str | None = None,
        base_url: str | None = None,
        name: str | None = None,
    ) -> None:
        """Configure the adapter.

        Args:
            model: Vendor model identifier.
            tier: Cost tier this provider occupies.
            api_key: Vendor API key; ``None`` defers to the SDK's own env-var
                lookup (``OPENAI_API_KEY`` when ``base_url`` is unset).
            base_url: Override the API endpoint. ``None`` targets the real
                OpenAI API; an OpenAI-compatible vendor endpoint (see
                :mod:`.openai_compatible`) works unchanged otherwise.
            name: Registry identity. Defaults to ``f"openai:{model}"``;
                subclasses pointed at another vendor should pass their own.
        """
        self.name = name or f"openai:{model}"
        self.tier = tier
        self.capabilities = (
            ProviderCapability.TOOLS
            | ProviderCapability.STREAMING
            | ProviderCapability.JSON_MODE
        )
        self._model = model
        self._api_key = api_key
        self._base_url = base_url
        self._counter = TokenCounter()

    @override
    def complete(self, request: CompletionRequest) -> CompletionResponse:
        import openai

        client = openai.OpenAI(api_key=self._api_key, base_url=self._base_url)
        response = client.chat.completions.create(**self._build_kwargs(request))
        return self._to_response(response)

    @override
    async def acomplete(self, request: CompletionRequest) -> CompletionResponse:
        import openai

        client = openai.AsyncOpenAI(api_key=self._api_key, base_url=self._base_url)
        response = await client.chat.completions.create(**self._build_kwargs(request))
        return self._to_response(response)

    @override
    def estimate_tokens(self, request: CompletionRequest) -> int:
        return self._counter.estimate(request)

    @override
    def classify_error(self, exc: Exception) -> ErrorClass:
        """Map OpenAI SDK rate-limit/API errors onto normalised classes."""
        import openai

        if isinstance(exc, openai.RateLimitError):
            # OpenAI reports both throttling and hard quota exhaustion as 429;
            # the ``insufficient_quota`` code distinguishes the latter.
            if getattr(exc, "code", None) == "insufficient_quota":
                return ErrorClass.QUOTA
            return ErrorClass.RATE_LIMIT
        if isinstance(exc, openai.AuthenticationError | openai.PermissionDeniedError):
            return ErrorClass.AUTH
        if isinstance(exc, openai.BadRequestError):
            return ErrorClass.INVALID
        if isinstance(exc, openai.APIStatusError):
            return self._classify_status(exc.status_code)
        if isinstance(exc, openai.APIConnectionError):
            return ErrorClass.TRANSIENT
        return ErrorClass.TRANSIENT

    # -- translation helpers --------------------------------------------- #

    def _build_kwargs(self, request: CompletionRequest) -> dict[str, Any]:
        """Translate a :class:`CompletionRequest` into ``chat.completions`` kwargs."""
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": request.max_tokens or _DEFAULT_MAX_TOKENS,
            "messages": [self._to_openai_message(m) for m in request.messages],
        }
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        if request.tools:
            kwargs["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
                for tool in request.tools
            ]
        return kwargs

    @staticmethod
    def _to_openai_message(message: Message) -> dict[str, Any]:
        """Map one :class:`Message` onto an OpenAI chat message dict."""
        if message.role is Role.TOOL and message.tool_result is not None:
            return {
                "role": "tool",
                "tool_call_id": message.tool_result.call_id,
                "content": message.tool_result.content,
            }
        if message.tool_calls:
            return {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.name,
                            "arguments": json.dumps(call.arguments),
                        },
                    }
                    for call in message.tool_calls
                ],
            }
        return {"role": message.role.value, "content": message.content or ""}

    def _to_response(self, response: Any) -> CompletionResponse:
        """Translate an OpenAI chat completion into a :class:`CompletionResponse`."""
        choice = response.choices[0].message
        tool_calls: list[ToolCall] = []
        for call in choice.tool_calls or []:
            tool_calls.append(
                ToolCall(
                    id=call.id,
                    name=call.function.name,
                    arguments=json.loads(call.function.arguments or "{}"),
                )
            )

        message = Message(
            role=Role.ASSISTANT,
            content=choice.content,
            tool_calls=tuple(tool_calls),
        )
        usage = Usage(
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
        )
        return CompletionResponse(
            message=message,
            usage=usage,
            provider_name=self.name,
            tier=self.tier,
        )

    @staticmethod
    def _classify_status(status_code: int) -> ErrorClass:
        """Map an HTTP status code onto a normalised :class:`ErrorClass`."""
        if status_code == 429:
            return ErrorClass.RATE_LIMIT
        if status_code in (401, 403):
            return ErrorClass.AUTH
        if status_code >= 500:
            return ErrorClass.TRANSIENT
        return ErrorClass.INVALID
