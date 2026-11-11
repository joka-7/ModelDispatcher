import { afterEach, describe, expect, it, vi } from "vitest";

import { completeOllama, completeWithToolsOllama, streamOllama } from "../../src/providers/ollama.js";
import { history, mockReply, quote, sentBody } from "./toolFixtures.js";
import type { ProviderCallConfig } from "../../src/types.js";

const cfg: ProviderCallConfig = { provider: "ollama", apiKey: "", model: "llama3.2", ollamaUrl: "http://localhost:11434" };

describe("completeOllama", () => {
  const originalFetch = globalThis.fetch;
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("posts to /api/chat with no auth header and reads message.content", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ message: { content: "hi" } })));
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const text = await completeOllama(cfg, [{ role: "user", content: "hello" }]);

    expect(text).toBe("hi");
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://localhost:11434/api/chat");
    expect((init.headers as Record<string, string> | undefined)?.Authorization).toBeUndefined();
  });

  it("rejects a non-HTTPS remote ollamaUrl before ever calling fetch", async () => {
    const fetchMock = vi.fn();
    globalThis.fetch = fetchMock as unknown as typeof fetch;
    const remote: ProviderCallConfig = { ...cfg, ollamaUrl: "http://example.com:11434" };

    await expect(completeOllama(remote, [{ role: "user", content: "hi" }])).rejects.toThrow(/HTTPS/);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("streamOllama", () => {
  const originalFetch = globalThis.fetch;
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("accumulates message.content across NDJSON lines", async () => {
    const ndjson =
      '{"message":{"content":"Hel"},"done":false}\n' + '{"message":{"content":"lo"},"done":false}\n' + '{"done":true}\n';
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(ndjson));
        controller.close();
      },
    });
    globalThis.fetch = vi.fn().mockResolvedValue(new Response(stream)) as unknown as typeof fetch;

    const chunks: string[] = [];
    const full = await streamOllama(cfg, [{ role: "user", content: "hi" }], (c) => chunks.push(c));

    expect(chunks).toEqual(["Hel", "Hello"]);
    expect(full).toBe("Hello");
  });
});

describe("completeWithToolsOllama", () => {
  const originalFetch = globalThis.fetch;
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  const cfg: ProviderCallConfig = { provider: "ollama", apiKey: "", model: "llama3.2", ollamaUrl: "http://localhost:11434" };

  it("sends arguments as objects and names each tool result", async () => {
    const fetchMock = mockReply({
      message: { content: "", tool_calls: [{ function: { name: "get_quote", arguments: { symbol: "MSFT" } } }] },
    });

    const turn = await completeWithToolsOllama(cfg, history, [quote], {});

    const body = sentBody(fetchMock);
    expect((body["messages"] as unknown[]).slice(2)).toEqual([
      {
        role: "assistant",
        content: "Checking.",
        tool_calls: [
          { function: { name: "get_quote", arguments: { symbol: "AAPL" } } },
          { function: { name: "get_portfolio", arguments: {} } },
        ],
      },
      { role: "tool", tool_name: "get_quote", content: "190.5" },
      { role: "tool", tool_name: "get_portfolio", content: "tool error: locked" },
    ]);
    expect(turn).toEqual({ text: "", toolCalls: [{ id: "", name: "get_quote", arguments: { symbol: "MSFT" } }] });
  });
});
