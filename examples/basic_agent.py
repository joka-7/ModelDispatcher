"""Minimal, runnable example of ModelDispatcher's agent loop.

No API keys required — this uses the keyless :class:`MockProvider`, so it runs
anywhere in a couple of seconds. It walks through everything an app needs to
do to use the gateway as an AI agent:

    1. Register one or more model providers.
    2. Build a `ModelGateway` once at startup.
    3. Register the tool(s) the agent may call.
    4. Describe the caller as a tenant (quota/credentials are scoped per tenant).
    5. Dispatch a prompt — the agent loop decides on its own whether to call a
       tool, and keeps going until it has a final answer.

Run:
    pip install -e .        # from the repo root (or `pip install model-dispatcher`)
    python examples/basic_agent.py

To go live against a real model, swap `MockProvider` for `OpenAIProvider` /
`AnthropicProvider` / `GeminiProvider` (see the comment at that line) — nothing
else in this file changes.
"""

from __future__ import annotations

from model_dispatcher import (
    CompletionRequest,
    Message,
    ModelGateway,
    ModelTier,
    ProviderRegistry,
    Role,
    TenantContext,
    TenantId,
    TenantQuota,
    Tool,
    ToolCall,
    ToolRegistry,
    ToolSpec,
)
from model_dispatcher.providers import MockProvider
from model_dispatcher.types import JSONValue


def get_weather(args: dict[str, JSONValue]) -> str:
    """The actual Python function the agent is allowed to call."""
    return f"It is 21C and sunny in {args['city']}."


def build_weather_tool() -> Tool:
    """Pair the callable above with the JSON-Schema spec the model sees."""
    spec = ToolSpec(
        name="get_weather",
        description="Look up the current weather for a city.",
        parameters={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
    )
    return Tool(spec=spec, handler=get_weather)


def main() -> None:
    """Wire up a gateway, register a tool, and dispatch one prompt through it."""
    # 1. Providers. MockProvider is keyless and scripted here: turn 1 asks for
    #    the tool, turn 2 answers using the tool's result. Swap this line for
    #    `OpenAIProvider(api_key=...)` / `AnthropicProvider(api_key=...)` /
    #    `GeminiProvider(api_key=...)` to hit a real model — everything below
    #    is identical either way.
    provider = MockProvider(
        "mock:free",
        tier=ModelTier.FREE,
        scripted=[
            Message(
                role=Role.ASSISTANT,
                tool_calls=(
                    ToolCall(
                        id="call-1", name="get_weather", arguments={"city": "Paris"}
                    ),
                ),
            ),
            Message(role=Role.ASSISTANT, content="It's 21C and sunny in Paris."),
        ],
    )
    providers = ProviderRegistry()
    providers.register(provider)

    # 2. Build the gateway once at app startup; reuse it for every request.
    gateway = ModelGateway.create(providers)

    # 3. Register the tool(s) available for this run.
    tools = ToolRegistry()
    tools.register(build_weather_tool())

    # 4. Who's asking — quota and credential resolution are scoped per tenant.
    tenant = TenantContext(
        tenant_id=TenantId("demo-user"),
        quota=TenantQuota(
            requests_per_min=20, tokens_per_min=40_000, tokens_per_day=1_000_000
        ),
    )

    # 5. Dispatch. The agent loop calls get_weather on its own before answering.
    request = CompletionRequest(
        messages=(Message(role=Role.USER, content="What's the weather in Paris?"),),
        tenant=tenant.tenant_id,
        tools=(build_weather_tool().spec,),
    )
    result = gateway.dispatch(request, tenant, tools=tools)

    print(f"stop_reason: {result.stop_reason.value}")
    print(f"answer:      {result.final_message.content}")
    print(f"turns:       {len(result.steps)}")
    for i, step in enumerate(result.steps, start=1):
        served_by = [a.provider_name for a in step.attempts if a.error_class is None]
        print(f"  turn {i} served by: {served_by}")


if __name__ == "__main__":
    main()
