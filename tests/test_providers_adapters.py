"""Unit tests for the OpenAI/Anthropic adapter translation layers.

Translation and token estimation are exercised without any SDK installed (the
vendor import happens only inside ``complete``/``classify_error``). The
error-normalization tests are skipped unless the corresponding SDK extra is
present, so CI stays fast and dependency-free while the mapping is still covered
when the extras are installed.
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
    ToolSpec,
)
from model_dispatcher.providers.anthropic_provider import AnthropicProvider
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


def test_estimate_tokens_is_positive() -> None:
    assert AnthropicProvider(model="claude-opus-4-8").estimate_tokens(_request()) > 0
    assert OpenAIProvider(model="gpt-4o-mini").estimate_tokens(_request()) > 0


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
