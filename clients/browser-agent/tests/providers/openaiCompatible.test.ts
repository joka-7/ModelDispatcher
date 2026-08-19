import { afterEach, describe, expect, it, vi } from "vitest";

import { completeOpenAICompatible, streamOpenAICompatible } from "../../src/providers/openaiCompatible.js";
import type { AgentConfig } from "../../src/types.js";

const cfg: AgentConfig = { provider: "openai", apiKey: "sk-x", model: "gpt-4o-mini", ollamaUrl: "" };

describe("completeOpenAICompatible", () => {
  const originalFetch = globalThis.fetch;
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("hits Groq's base URL when provider is groq, with a Bearer key and JSON mode", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ choices: [{ message: { content: "hi" } }] })));
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const text = await completeOpenAICompatible("groq", cfg, [{ role: "user", content: "hello" }], { jsonMode: true });

    expect(text).toBe("hi");
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("https://api.groq.com/openai/v1/chat/completions");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer sk-x");
    const body = JSON.parse(init.body as string);
    expect(body.response_format).toEqual({ type: "json_object" });
  });

  it("prepends a system message from systemInstruction when no system turn exists", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ choices: [{ message: {} }] })));
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    await completeOpenAICompatible("openai", cfg, [{ role: "user", content: "hi" }], { systemInstruction: "be terse" });
    const body = JSON.parse((fetchMock.mock.calls[0]![1] as RequestInit).body as string);
    expect(body.messages).toEqual([
      { role: "system", content: "be terse" },
      { role: "user", content: "hi" },
    ]);
  });
});

describe("streamOpenAICompatible", () => {
  const originalFetch = globalThis.fetch;
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("accumulates delta text and stops at [DONE]", async () => {
    const sse =
      'data: {"choices":[{"delta":{"content":"Hel"}}]}\n\n' +
      'data: {"choices":[{"delta":{"content":"lo"}}]}\n\n' +
      "data: [DONE]\n\n";
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(sse));
        controller.close();
      },
    });
    globalThis.fetch = vi.fn().mockResolvedValue(new Response(stream)) as unknown as typeof fetch;

    const chunks: string[] = [];
    const full = await streamOpenAICompatible("openai", cfg, [{ role: "user", content: "hi" }], (c) => chunks.push(c));

    expect(chunks).toEqual(["Hel", "Hello"]);
    expect(full).toBe("Hello");
  });
});
