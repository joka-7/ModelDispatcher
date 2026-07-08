"""Google Gemini provider strategy.

Adapter for Google Gemini models built on the current ``google-genai`` SDK (an
optional extra, imported lazily inside method bodies so importing the core
package never requires the vendor dependency). The older ``google-generativeai``
package is fully deprecated upstream (no further updates or bug fixes), so this
adapter deliberately targets its replacement rather than the retired SDK.

Gemini's chat format differs from Anthropic/OpenAI in two ways this module has
to bridge: turns use ``role="model"`` instead of ``"assistant"``, and a function
call/response pair is matched by *name*, not by an opaque call id — Gemini
itself does not require (or reliably return) an id for a function call. Call ids
are still synthesised locally so the rest of the library's tool-loop machinery
(which addresses tool results by :class:`~model_dispatcher.types.ToolCall.id`)
works unchanged; the id never needs to round-trip to Gemini itself.
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

__all__ = ["GeminiProvider"]

_DEFAULT_MAX_TOKENS = 4096


class GeminiProvider(ModelProvider):
    """Adapter for Google Gemini models."""

    def __init__(
        self,
        *,
        model: str,
        tier: ModelTier = ModelTier.CHEAP,
        api_key: str | None = None,
    ) -> None:
        self.name = f"gemini:{model}"
        self.tier = tier
        self.capabilities = (
            ProviderCapability.TOOLS
            | ProviderCapability.STREAMING
            | ProviderCapability.VISION
            | ProviderCapability.JSON_MODE
        )
        self._model = model
        self._api_key = api_key
        self._counter = TokenCounter()

    @override
    def complete(self, request: CompletionRequest) -> CompletionResponse:
        from google import genai

        client = genai.Client(api_key=self._api_key)
        system, contents = self._build_contents(request)
        response = client.models.generate_content(
            model=self._model,
            contents=contents,
            config=self._build_config(request, system),
        )
        return self._to_response(response)

    @override
    async def acomplete(self, request: CompletionRequest) -> CompletionResponse:
        from google import genai

        client = genai.Client(api_key=self._api_key)
        system, contents = self._build_contents(request)
        response = await client.aio.models.generate_content(
            model=self._model,
            contents=contents,
            config=self._build_config(request, system),
        )
        return self._to_response(response)

    @override
    def estimate_tokens(self, request: CompletionRequest) -> int:
        return self._counter.estimate(request)

    @override
    def classify_error(self, exc: Exception) -> ErrorClass:
        """Map ``google.genai`` API errors onto normalised classes."""
        from google.genai import errors

        if isinstance(exc, errors.APIError):
            return self._classify_status(exc.code)
        return ErrorClass.TRANSIENT

    # -- translation helpers --------------------------------------------- #

    def _build_config(self, request: CompletionRequest, system: str) -> Any:
        """Build the ``GenerateContentConfig`` for one request."""
        from google.genai import types

        kwargs: dict[str, Any] = {
            "max_output_tokens": request.max_tokens or _DEFAULT_MAX_TOKENS,
        }
        if system:
            kwargs["system_instruction"] = system
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        if request.tools:
            kwargs["tools"] = [
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(
                            name=tool.name,
                            description=tool.description,
                            parameters_json_schema=tool.parameters,
                        )
                        for tool in request.tools
                    ]
                )
            ]
        return types.GenerateContentConfig(**kwargs)

    def _build_contents(self, request: CompletionRequest) -> tuple[str, list[Any]]:
        """Split system text out and map the rest to Gemini ``Content`` turns.

        Gemini takes the system prompt as a config field, not a message, and
        represents tool calls/results as typed ``Part`` variants under
        ``role="model"``/``"user"`` respectively. A tool result is matched back
        to its originating call by *name*: since :class:`ToolResult` only carries
        the synthesised call id, this method scans the already-seen messages in
        the same request for the :class:`ToolCall` that minted that id.
        """
        from google.genai import types

        system_parts: list[str] = []
        contents: list[Any] = []
        call_names_by_id: dict[str, str] = {}

        for message in request.messages:
            if message.role is Role.SYSTEM:
                if message.content:
                    system_parts.append(message.content)
            elif message.role is Role.TOOL and message.tool_result is not None:
                result = message.tool_result
                name = call_names_by_id.get(result.call_id, result.call_id)
                payload: dict[str, JSONValue] = (
                    {"error": result.content}
                    if result.is_error
                    else {"result": result.content}
                )
                contents.append(
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_function_response(
                                name=name, response=payload
                            )
                        ],
                    )
                )
            elif message.tool_calls:
                for call in message.tool_calls:
                    call_names_by_id[call.id] = call.name
                parts = (
                    [types.Part.from_text(text=message.content)]
                    if message.content
                    else []
                )
                parts.extend(
                    types.Part.from_function_call(name=call.name, args=call.arguments)
                    for call in message.tool_calls
                )
                contents.append(types.Content(role="model", parts=parts))
            else:
                role = "model" if message.role is Role.ASSISTANT else "user"
                contents.append(
                    types.Content(
                        role=role,
                        parts=[types.Part.from_text(text=message.content or "")],
                    )
                )
        return "\n".join(system_parts), contents

    def _to_response(self, response: Any) -> CompletionResponse:
        """Translate a Gemini response into a :class:`CompletionResponse`."""
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        candidate = response.candidates[0] if response.candidates else None
        parts = candidate.content.parts if candidate and candidate.content else []

        for index, part in enumerate(parts or []):
            if part.text:
                text_parts.append(part.text)
            elif part.function_call is not None:
                call_id = part.function_call.id or f"call_{index}"
                arguments: dict[str, JSONValue] = dict(part.function_call.args or {})
                tool_calls.append(
                    ToolCall(
                        id=call_id, name=part.function_call.name, arguments=arguments
                    )
                )

        message = Message(
            role=Role.ASSISTANT,
            content="".join(text_parts) or None,
            tool_calls=tuple(tool_calls),
        )
        usage_meta = response.usage_metadata
        usage = Usage(
            prompt_tokens=usage_meta.prompt_token_count if usage_meta else 0,
            completion_tokens=usage_meta.candidates_token_count if usage_meta else 0,
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
