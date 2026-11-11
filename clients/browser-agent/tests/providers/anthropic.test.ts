import { afterEach, describe, expect, it, vi } from "vitest";

import { completeAnthropic, completeWithToolsAnthropic, streamAnthropic } from "../../src/providers/anthropic.js";
import { history, mockReply, quote, sentBody } from "./toolFixtures.js";
import type { ProviderCallConfig } from "../../src/types.js";

const cfg: ProviderCallConfig = { provider: "anthropic", apiKey: "sk-ant-x", model: "claude-haiku-4-5", ollamaUrl: "" };

describe("completeAnthropic", () => {
  const originalFetch = globalThis.fetch;
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("sends the direct-browser-access header and system as a top-level field", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ content: [{ text: "hi" }] })));
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const text = await completeAnthropic(cfg, [{ role: "user", content: "hello" }], { systemInstruction: "be terse" });

    expect(text).toBe("hi");
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = init.headers as Record<string, string>;
    expect(headers["x-api-key"]).toBe("sk-ant-x");
    expect(headers["anthropic-dangerous-direct-browser-access"]).toBe("true");
    const body = JSON.parse(init.body as string);
    expect(body.system).toBe("be terse");
    expect(body.messages).toEqual([{ role: "user", content: "hello" }]);
  });
});

describe("streamAnthropic", () => {
  const originalFetch = globalThis.fetch;
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("only accumulates text from content_block_delta/text_delta events, ignoring others", async () => {
    const sse =
      'data: {"type":"message_start"}\n\n' +
      'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"Hel"}}\n\n' +
      'data: {"type":"ping"}\n\n' +
      'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"lo"}}\n\n' +
      'data: {"type":"message_stop"}\n\n';
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(sse));
        controller.close();
      },
    });
    globalThis.fetch = vi.fn().mockResolvedValue(new Response(stream)) as unknown as typeof fetch;

    const chunks: string[] = [];
    const full = await streamAnthropic(cfg, [{ role: "user", content: "hi" }], (c) => chunks.push(c));

    expect(chunks).toEqual(["Hel", "Hello"]);
    expect(full).toBe("Hello");
  });
});

describe("completeWithToolsAnthropic", () => {
  const originalFetch = globalThis.fetch;
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  const cfg: ProviderCallConfig = { provider: "anthropic", apiKey: "sk-ant", model: "claude-haiku-4-5", ollamaUrl: "" };

  it("sends tool_use blocks and all results in one user turn, flagging errors", async () => {
    const fetchMock = mockReply({ content: [{ type: "text", text: "190.5" }] });

    await completeWithToolsAnthropic(cfg, history, [quote], {});

    const body = sentBody(fetchMock);
    expect(body["system"]).toBe("Be brief.");
    expect(body["tools"]).toEqual([{ name: "get_quote", description: "Latest price", input_schema: quote.parameters }]);
    expect((body["messages"] as unknown[]).slice(1)).toEqual([
      {
        role: "assistant",
        content: [
          { type: "text", text: "Checking." },
          { type: "tool_use", id: "c1", name: "get_quote", input: { symbol: "AAPL" } },
          { type: "tool_use", id: "c2", name: "get_portfolio", input: {} },
        ],
      },
      {
        role: "user",
        content: [
          { type: "tool_result", tool_use_id: "c1", content: "190.5" },
          { type: "tool_result", tool_use_id: "c2", content: "tool error: locked", is_error: true },
        ],
      },
    ]);
  });

  it("decodes text and tool_use blocks", async () => {
    mockReply({
      content: [
        { type: "text", text: "Let me look." },
        { type: "tool_use", id: "tu_1", name: "get_quote", input: { symbol: "MSFT" } },
      ],
    });

    const turn = await completeWithToolsAnthropic(cfg, history.slice(0, 2), [quote], {});

    expect(turn).toEqual({ text: "Let me look.", toolCalls: [{ id: "tu_1", name: "get_quote", arguments: { symbol: "MSFT" } }] });
  });

  it.each([
    ["a refusal", { stop_reason: "refusal", content: [] }, "declined"],
    ["an empty turn", { stop_reason: "end_turn", content: [] }, "empty turn"],
    [
      "a call cut off by the token limit",
      { stop_reason: "max_tokens", content: [{ type: "tool_use", id: "t", name: "get_quote", input: {} }] },
      "out of tokens",
    ],
  ])("throws on %s, so the loop falls back", async (_case, reply, message) => {
    mockReply(reply);

    await expect(completeWithToolsAnthropic(cfg, history.slice(0, 2), [quote], {})).rejects.toThrow(message);
  });
});
