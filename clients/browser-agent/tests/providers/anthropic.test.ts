import { afterEach, describe, expect, it, vi } from "vitest";

import { completeAnthropic, streamAnthropic } from "../../src/providers/anthropic.js";
import type { AgentConfig } from "../../src/types.js";

const cfg: AgentConfig = { provider: "anthropic", apiKey: "sk-ant-x", model: "claude-haiku-4-5", ollamaUrl: "" };

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
