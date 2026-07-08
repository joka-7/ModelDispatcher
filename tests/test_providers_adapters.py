"""Unit tests for the OpenAI/Anthropic/Gemini adapter translation layers.

Translation and token estimation are exercised without any SDK installed (the
vendor import happens only inside ``complete``/``classify_error``), except for
Gemini's ``_build_contents``/``_build_config``, which construct real
``google.genai.types`` objects internally and so need that extra installed —
those two are explicitly gated with ``importorskip``. The error-normalization
tests are skipped unless the corresponding SDK extra is present, so CI stays
fast and dependency-free while the mapping is still covered when the extras
are installed.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from model_dispatcher import (
    CompletionRequest,
    Message,
    Role,
    TenantId,
    ToolCall,
    ToolResult,
    ToolSpec,
)
from model_dispatcher.providers.anthropic_provider import AnthropicProvider
from model_dispatcher.providers.gemini_provider import GeminiProvider
from model_dispatcher.providers.openai_provider import OpenAIProvider


def _request() -> CompletionRequest:
    return CompletionRequest(
        messages=(
            Message(role=Role.SYSTEM, content="be terse"),
            Message(role=Role.USER, content="hi"),
        ),
        tenant=TenantId("t"),
        tools=(ToolSpec(name="f", description="d", parameters={"type": "object"}),),
    )


def test_anthropic_split_extracts_system_and_maps_tools() -> None:
    provider = AnthropicProvider(model="claude-opus-4-8")
    request = CompletionRequest(
        messages=(
            Message(role=Role.SYSTEM, content="sys"),
            Message(
                role=Role.ASSISTANT,
                tool_calls=(ToolCall(id="c1", name="f", arguments={"x": 1}),),
            ),
        ),
        tenant=TenantId("t"),
    )
    system, messages = provider._split_messages(request)
    assert system == "sys"
    assert messages[0]["role"] == "assistant"
    assert messages[0]["content"][0]["type"] == "tool_use"


def test_anthropic_build_kwargs_moves_system_and_tools() -> None:
    provider = AnthropicProvider(model="claude-opus-4-8")
    kwargs = provider._build_kwargs(_request())
    assert kwargs["system"] == "be terse"
    assert kwargs["model"] == "claude-opus-4-8"
    assert kwargs["tools"][0]["name"] == "f"


def test_anthropic_to_response_reads_blocks_and_usage() -> None:
    provider = AnthropicProvider(model="claude-opus-4-8")
    fake = SimpleNamespace(
        content=[
            SimpleNamespace(type="text", text="hello "),
            SimpleNamespace(type="tool_use", id="c1", name="f", input={"x": 1}),
        ],
        usage=SimpleNamespace(input_tokens=7, output_tokens=3),
    )
    response = provider._to_response(fake)
    assert response.message.content == "hello "
    assert response.message.tool_calls[0].name == "f"
    assert response.usage.total_tokens == 10


def test_openai_message_shapes() -> None:
    provider = OpenAIProvider(model="gpt-4o-mini")
    tool_call_msg = Message(
        role=Role.ASSISTANT,
        tool_calls=(ToolCall(id="c1", name="f", arguments={"x": 1}),),
    )
    mapped = provider._to_openai_message(tool_call_msg)
    assert mapped["tool_calls"][0]["function"]["name"] == "f"


def test_openai_to_response_parses_tool_calls() -> None:
    provider = OpenAIProvider(model="gpt-4o-mini")
    fake = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=None,
                    tool_calls=[
                        SimpleNamespace(
                            id="c1",
                            function=SimpleNamespace(name="f", arguments='{"x": 1}'),
                        )
                    ],
                )
            )
        ],
        usage=SimpleNamespace(prompt_tokens=5, completion_tokens=2),
    )
    response = provider._to_response(fake)
    assert response.message.tool_calls[0].arguments == {"x": 1}
    assert response.usage.total_tokens == 7


def test_gemini_build_contents_maps_system_and_round_trips_tool_calls() -> None:
    pytest.importorskip("google.genai")
    provider = GeminiProvider(model="gemini-2.0-flash")
    request = CompletionRequest(
        messages=(
            Message(role=Role.SYSTEM, content="sys"),
            Message(role=Role.USER, content="weather in Rome?"),
            Message(
                role=Role.ASSISTANT,
                tool_calls=(
                    ToolCall(id="call_0", name="f", arguments={"city": "Rome"}),
                ),
            ),
            Message(
                role=Role.TOOL,
                tool_result=ToolResult(call_id="call_0", content="Sunny, 24C"),
            ),
        ),
        tenant=TenantId("t"),
    )
    system, contents = provider._build_contents(request)
    assert system == "sys"
    assert contents[1].role == "model"
    assert contents[1].parts[0].function_call.name == "f"
    # The tool result is matched back to its call by *name*, recovered from the
    # assistant turn earlier in the same request (Gemini has no call-id concept).
    assert contents[2].role == "user"
    assert contents[2].parts[0].function_response.name == "f"
    assert contents[2].parts[0].function_response.response == {"result": "Sunny, 24C"}


def test_gemini_build_config_moves_system_and_tools() -> None:
    pytest.importorskip("google.genai")
    provider = GeminiProvider(model="gemini-2.0-flash")
    request = _request()
    system, _ = provider._build_contents(request)
    config = provider._build_config(request, system)
    assert config.system_instruction == "be terse"
    assert config.tools[0].function_declarations[0].name == "f"


def test_gemini_to_response_reads_text_and_usage() -> None:
    provider = GeminiProvider(model="gemini-2.0-flash")
    fake = SimpleNamespace(
        candidates=[
            SimpleNamespace(
                content=SimpleNamespace(
                    parts=[SimpleNamespace(text="hello ", function_call=None)]
                )
            )
        ],
        usage_metadata=SimpleNamespace(prompt_token_count=7, candidates_token_count=3),
    )
    response = provider._to_response(fake)
    assert response.message.content == "hello "
    assert response.usage.total_tokens == 10


def test_gemini_to_response_parses_function_call() -> None:
    provider = GeminiProvider(model="gemini-2.0-flash")
    fake = SimpleNamespace(
        candidates=[
            SimpleNamespace(
                content=SimpleNamespace(
                    parts=[
                        SimpleNamespace(
                            text=None,
                            function_call=SimpleNamespace(
                                id=None, name="f", args={"x": 1}
                            ),
                        )
                    ]
                )
            )
        ],
        usage_metadata=SimpleNamespace(prompt_token_count=5, candidates_token_count=2),
    )
    response = provider._to_response(fake)
    assert response.message.tool_calls[0].name == "f"
    assert response.message.tool_calls[0].arguments == {"x": 1}
    # No id supplied by the model -> a synthetic one is minted so the rest of
    # the pipeline (which addresses tool results by id) still has one to use.
    assert response.message.tool_calls[0].id


def test_gemini_classify_error_maps_status_codes() -> None:
    genai_errors = pytest.importorskip("google.genai.errors")
    provider = GeminiProvider(model="gemini-2.0-flash")
    from model_dispatcher.types import ErrorClass

    rate_limited = genai_errors.ClientError(429, {"error": {"message": "quota"}})
    unauthorized = genai_errors.ClientError(401, {"error": {"message": "bad key"}})
    down = genai_errors.ServerError(503, {"error": {"message": "down"}})

    assert provider.classify_error(rate_limited) is ErrorClass.RATE_LIMIT
    assert provider.classify_error(unauthorized) is ErrorClass.AUTH
    assert provider.classify_error(down) is ErrorClass.TRANSIENT


def test_estimate_tokens_is_positive() -> None:
    assert AnthropicProvider(model="claude-opus-4-8").estimate_tokens(_request()) > 0
    assert OpenAIProvider(model="gpt-4o-mini").estimate_tokens(_request()) > 0
    assert GeminiProvider(model="gemini-2.0-flash").estimate_tokens(_request()) > 0


def test_anthropic_classify_error_maps_rate_limit() -> None:
    anthropic = pytest.importorskip("anthropic")
    provider = AnthropicProvider(model="claude-opus-4-8")
    exc = anthropic.RateLimitError.__new__(anthropic.RateLimitError)
    from model_dispatcher.types import ErrorClass

    assert provider.classify_error(exc) is ErrorClass.RATE_LIMIT


def test_openai_classify_error_maps_auth() -> None:
    openai = pytest.importorskip("openai")
    provider = OpenAIProvider(model="gpt-4o-mini")
    exc = openai.AuthenticationError.__new__(openai.AuthenticationError)
    from model_dispatcher.types import ErrorClass

    assert provider.classify_error(exc) is ErrorClass.AUTH
