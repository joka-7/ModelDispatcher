"""Anthropic provider strategy.

Adapter for Anthropic Claude models built on the official ``anthropic`` SDK
(an optional extra, imported lazily inside method bodies so importing the core
package never requires the vendor dependency). Vendor exceptions are normalised
into the shared :class:`ErrorClass` taxonomy so the fallback chain can reason
about failures without importing anything from ``anthropic``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, override

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

if TYPE_CHECKING:
    from ..types import JSONValue

__all__ = ["AnthropicProvider"]

_DEFAULT_MODEL = "claude-opus-4-8"
_DEFAULT_MAX_TOKENS = 4096


class AnthropicProvider(ModelProvider):
    """Adapter for Anthropic Claude models."""

    def __init__(
        self,
        *,
        model: str = _DEFAULT_MODEL,
        tier: ModelTier = ModelTier.PREMIUM,
        api_key: str | None = None,
    ) -> None:
        self.name = f"anthropic:{model}"
        self.tier = tier
        self.capabilities = (
            ProviderCapability.TOOLS
            | ProviderCapability.STREAMING
            | ProviderCapability.VISION
        )
        self._model = model
        self._api_key = api_key
        self._counter = TokenCounter()

    @override
    def complete(
        self, request: CompletionRequest, *, api_key: str | None = None
    ) -> CompletionResponse:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key or self._api_key)
        response = client.messages.create(**self._build_kwargs(request))
        return self._to_response(response)

    @override
    async def acomplete(
        self, request: CompletionRequest, *, api_key: str | None = None
    ) -> CompletionResponse:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=api_key or self._api_key)
        response = await client.messages.create(**self._build_kwargs(request))
        return self._to_response(response)

    @override
    def estimate_tokens(self, request: CompletionRequest) -> int:
        return self._counter.estimate(request)

    @override
    def classify_error(self, exc: Exception) -> ErrorClass:
        """Map Anthropic SDK rate-limit/status errors onto normalised classes."""
        import anthropic

        if isinstance(exc, anthropic.RateLimitError):
            return ErrorClass.RATE_LIMIT
        if isinstance(exc, anthropic.AuthenticationError):
            return ErrorClass.AUTH
        if isinstance(exc, anthropic.BadRequestError):
            # Anthropic surfaces exhausted credits as a billing error (HTTP 400).
            if getattr(exc, "type", None) == "billing_error":
                return ErrorClass.QUOTA
            return ErrorClass.INVALID
        if isinstance(exc, anthropic.APIStatusError):
            return self._classify_status(exc.status_code)
        if isinstance(exc, anthropic.APIConnectionError):
            return ErrorClass.TRANSIENT
        return ErrorClass.TRANSIENT

    # -- translation helpers --------------------------------------------- #

    def _build_kwargs(self, request: CompletionRequest) -> dict[str, Any]:
        """Translate a :class:`CompletionRequest` into ``messages.create`` kwargs."""
        system, messages = self._split_messages(request)
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": request.max_tokens or _DEFAULT_MAX_TOKENS,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        if request.tools:
            kwargs["tools"] = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.parameters,
                }
                for tool in request.tools
            ]
        return kwargs

    def _split_messages(
        self, request: CompletionRequest
    ) -> tuple[str, list[dict[str, Any]]]:
        """Split system text out and map the rest to Anthropic message dicts.

        Anthropic takes the system prompt as a top-level ``system`` argument
        rather than a message, and represents tool calls / results as typed
        content blocks — this method performs that structural conversion.
        """
        system_parts: list[str] = []
        messages: list[dict[str, Any]] = []
        for message in request.messages:
            if message.role is Role.SYSTEM:
                if message.content:
                    system_parts.append(message.content)
            elif message.role is Role.TOOL and message.tool_result is not None:
                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": message.tool_result.call_id,
                                "content": message.tool_result.content,
                                "is_error": message.tool_result.is_error,
                            }
                        ],
                    }
                )
            elif message.tool_calls:
                blocks: list[dict[str, Any]] = []
                if message.content:
                    blocks.append({"type": "text", "text": message.content})
                blocks.extend(
                    {
                        "type": "tool_use",
                        "id": call.id,
                        "name": call.name,
                        "input": call.arguments,
                    }
                    for call in message.tool_calls
                )
                messages.append({"role": "assistant", "content": blocks})
            else:
                messages.append(
                    {"role": message.role.value, "content": message.content or ""}
                )
        return "\n".join(system_parts), messages

    def _to_response(self, response: Any) -> CompletionResponse:
        """Translate an Anthropic ``Message`` into a :class:`CompletionResponse`."""
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                arguments: dict[str, JSONValue] = dict(block.input)
                tool_calls.append(
                    ToolCall(id=block.id, name=block.name, arguments=arguments)
                )

        message = Message(
            role=Role.ASSISTANT,
            content="".join(text_parts) or None,
            tool_calls=tuple(tool_calls),
        )
        usage = Usage(
            prompt_tokens=response.usage.input_tokens,
            completion_tokens=response.usage.output_tokens,
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
