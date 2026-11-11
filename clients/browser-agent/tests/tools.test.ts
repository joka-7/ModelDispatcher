import { afterEach, describe, expect, it, vi } from "vitest";

import { AllProvidersExhaustedError, NoProviderConfiguredError } from "../src/agent.js";
import { runWithTools, type Tool } from "../src/tools.js";
import type { AgentConfig, ToolChatMessage } from "../src/types.js";

const originalFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = originalFetch;
});

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

/** An OpenAI chat-completions reply: text, or one call per [name, args]. */
function openAIReply(text: string | null, calls: [string, Record<string, unknown>][] = []): Response {
  return jsonResponse({
    choices: [
      {
        message: {
          content: text,
          ...(calls.length
            ? {
                tool_calls: calls.map(([name, args], i) => ({
                  id: `oa_${i}`,
                  type: "function",
                  function: { name, arguments: JSON.stringify(args) },
                })),
              }
            : {}),
        },
      },
    ],
  });
}

const openai: AgentConfig = { providers: [{ provider: "openai", model: "gpt-4o-mini", apiKeys: ["sk-1"] }], ollamaUrl: "" };
const question: ToolChatMessage[] = [{ role: "user", content: "How much AAPL do I hold?" }];

function quantityTool(run: Tool["run"] = () => "12 shares"): Tool {
  return {
    spec: {
      name: "get_quantity",
      description: "How many shares the user holds",
      parameters: { type: "object", properties: { symbol: { type: "string" } }, required: ["symbol"] },
    },
    run,
  };
}

function sentBodies(fetchMock: ReturnType<typeof vi.fn>): { messages: Record<string, unknown>[] }[] {
  return fetchMock.mock.calls.map(([, init]) => JSON.parse((init as RequestInit).body as string));
}

describe("runWithTools", () => {
  it("runs the requested tool on the device and returns the model's answer", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(openAIReply(null, [["get_quantity", { symbol: "AAPL" }]]))
      .mockResolvedValueOnce(openAIReply("You hold 12 shares of AAPL."));
    globalThis.fetch = fetchMock as unknown as typeof fetch;
    const run = vi.fn().mockReturnValue("12 shares");

    const out = await runWithTools(openai, question, { tools: [quantityTool(run)] });

    expect(run).toHaveBeenCalledWith({ symbol: "AAPL" });
    expect(out).toMatchObject({
      text: "You hold 12 shares of AAPL.",
      stopReason: "completed",
      toolsUsed: ["get_quantity"],
      provider: "openai",
      model: "gpt-4o-mini",
    });
    expect(sentBodies(fetchMock)[1]?.messages.at(-1)).toEqual({
      role: "tool",
      tool_call_id: "oa_0",
      content: "12 shares",
    });
  });

  it.each([
    ["an unknown tool", "no_such_tool", quantityTool(), "unknown tool: no_such_tool"],
    [
      "a tool that throws",
      "get_quantity",
      quantityTool(() => {
        throw new Error("store is locked");
      }),
      "tool error: store is locked",
    ],
  ])("hands %s back to the model as an error instead of failing", async (_case, name, tool, expected) => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(openAIReply(null, [[name, { symbol: "AAPL" }]]))
      .mockResolvedValueOnce(openAIReply("Sorry, I couldn't check that."));
    globalThis.fetch = fetchMock as unknown as typeof fetch;
    const seen = vi.fn();

    const out = await runWithTools(openai, question, { tools: [tool], onToolResult: seen });

    expect(out.stopReason).toBe("completed");
    expect(seen.mock.calls[0]?.[1]).toMatchObject({ isError: true, content: expected });
  });

  it("runs several tools from one turn in the order asked", async () => {
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce(
        openAIReply(null, [
          ["get_quantity", { symbol: "AAPL" }],
          ["get_quantity", { symbol: "MSFT" }],
        ]),
      )
      .mockResolvedValueOnce(openAIReply("done")) as unknown as typeof fetch;
    const order: string[] = [];

    await runWithTools(openai, question, {
      tools: [quantityTool((args) => (order.push(String(args["symbol"])), "1"))],
    });

    expect(order).toEqual(["AAPL", "MSFT"]);
  });

  it("stops after maxSteps turns that keep asking for tools", async () => {
    globalThis.fetch = vi
      .fn()
      .mockImplementation(() =>
        Promise.resolve(openAIReply(null, [["get_quantity", { symbol: "AAPL" }]])),
      ) as unknown as typeof fetch;

    const out = await runWithTools(openai, question, { tools: [quantityTool()], maxSteps: 2 });

    expect(out).toMatchObject({ stopReason: "max_steps", toolsUsed: ["get_quantity", "get_quantity"] });
  });

  it("hands the run to the next provider when one fails mid-conversation", async () => {
    const cfg: AgentConfig = {
      providers: [
        { provider: "openai", model: "gpt-4o-mini", apiKeys: ["sk-1"] },
        { provider: "anthropic", model: "claude-haiku-4-5", apiKeys: ["sk-ant"] },
      ],
      ollamaUrl: "",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(openAIReply(null, [["get_quantity", { symbol: "AAPL" }]]))
      .mockImplementation((url: string) =>
      Promise.resolve(
        url.includes("anthropic")
          ? jsonResponse({ content: [{ type: "text", text: "12 shares." }] })
          : jsonResponse({ error: { message: "bad key" } }, 401),
      ));
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const out = await runWithTools(cfg, question, { tools: [quantityTool()] });

    expect(out).toMatchObject({ text: "12 shares.", provider: "anthropic" });
    const anthropicBody = sentBodies(fetchMock).at(-1);
    expect(anthropicBody?.messages[1]).toEqual({
      role: "assistant",
      content: [{ type: "tool_use", id: "oa_0", name: "get_quantity", input: { symbol: "AAPL" } }],
    });
  });

  it("gives calls without a provider id an id unique in the run", async () => {
    const gemini: AgentConfig = { providers: [{ provider: "gemini", model: "gemini-2.5-flash", apiKeys: ["k"] }], ollamaUrl: "" };
    const call = { candidates: [{ content: { parts: [{ functionCall: { name: "get_quantity", args: { symbol: "A" } } }] } }] };
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(call))
      .mockResolvedValueOnce(jsonResponse(call))
      .mockResolvedValueOnce(jsonResponse({ candidates: [{ content: { parts: [{ text: "ok" }] } }] })) as unknown as typeof fetch;
    const ids: string[] = [];

    await runWithTools(gemini, question, { tools: [quantityTool()], onToolResult: (c) => ids.push(c.id) });

    expect(ids).toEqual(["call_0_0", "call_1_0"]);
  });

  it.each([
    ["nothing is configured", { providers: [], ollamaUrl: "" }, NoProviderConfiguredError],
    ["every provider fails", openai, AllProvidersExhaustedError],
  ])("raises when %s", async (_case, cfg, error) => {
    globalThis.fetch = vi.fn().mockResolvedValue(jsonResponse({ error: { message: "down" } }, 400)) as unknown as typeof fetch;

    await expect(runWithTools(cfg as AgentConfig, question, { tools: [quantityTool()] })).rejects.toThrow(error);
  });
});
