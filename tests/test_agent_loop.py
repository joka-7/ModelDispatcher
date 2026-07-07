"""Behavioral tests for the native agent tool-calling loop."""

from __future__ import annotations

from collections.abc import Callable

from model_dispatcher import (
    CompletionRequest,
    Message,
    ModelGateway,
    ModelTier,
    Role,
    StopReason,
    TenantContext,
    Tool,
    ToolCall,
    ToolRegistry,
    ToolSpec,
)
from model_dispatcher.providers import MockProvider
from model_dispatcher.types import JSONValue


def _weather_tool() -> Tool:
    def handler(args: dict[str, JSONValue]) -> str:
        return f"It is 21C in {args.get('city')}."

    spec = ToolSpec(
        name="get_weather",
        description="Look up the weather for a city.",
        parameters={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
    )
    return Tool(spec=spec, handler=handler)


def test_loop_executes_tool_then_returns_final_answer(
    make_gateway: Callable[..., ModelGateway],
    make_tenant: Callable[..., TenantContext],
) -> None:
    # Turn 1: model asks for the tool. Turn 2: model answers using the result.
    scripted = [
        Message(
            role=Role.ASSISTANT,
            tool_calls=(
                ToolCall(id="call-1", name="get_weather", arguments={"city": "Paris"}),
            ),
        ),
        Message(role=Role.ASSISTANT, content="The weather in Paris is 21C."),
    ]
    provider = MockProvider("mock:free", tier=ModelTier.FREE, scripted=scripted)
    gateway = make_gateway(provider)
    tenant = make_tenant()

    registry = ToolRegistry()
    registry.register(_weather_tool())
    request = CompletionRequest(
        messages=(Message(role=Role.USER, content="Weather in Paris?"),),
        tenant=tenant.tenant_id,
        tools=(_weather_tool().spec,),
    )

    result = gateway.dispatch(request, tenant, tools=registry)

    assert result.stop_reason is StopReason.COMPLETED
    assert result.final_message.content == "The weather in Paris is 21C."
    # Transcript: user, assistant(tool_call), tool(result), assistant(final).
    roles = [m.role for m in result.transcript]
    assert roles == [Role.USER, Role.ASSISTANT, Role.TOOL, Role.ASSISTANT]
    tool_message = result.transcript[2]
    assert tool_message.tool_result is not None
    assert "21C in Paris" in tool_message.tool_result.content
    assert len(result.steps) == 2  # two model turns


def test_loop_accumulates_usage_across_turns(
    make_gateway: Callable[..., ModelGateway],
    make_tenant: Callable[..., TenantContext],
) -> None:
    scripted = [
        Message(
            role=Role.ASSISTANT,
            tool_calls=(
                ToolCall(id="c1", name="get_weather", arguments={"city": "Rome"}),
            ),
        ),
        Message(role=Role.ASSISTANT, content="Sunny in Rome."),
    ]
    provider = MockProvider("mock:free", tier=ModelTier.FREE, scripted=scripted)
    gateway = make_gateway(provider)
    tenant = make_tenant()
    registry = ToolRegistry()
    registry.register(_weather_tool())
    request = CompletionRequest(
        messages=(Message(role=Role.USER, content="Weather in Rome?"),),
        tenant=tenant.tenant_id,
        tools=(_weather_tool().spec,),
    )

    result = gateway.dispatch(request, tenant, tools=registry)
    per_step = sum(s.usage.total_tokens for s in result.steps)
    assert result.usage.total_tokens == per_step
    assert result.usage.total_tokens > 0
