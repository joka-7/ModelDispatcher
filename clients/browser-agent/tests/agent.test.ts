import { afterEach, describe, expect, it, vi } from "vitest";

import { complete, streamChat, streamComplete } from "../src/agent.js";
import type { AgentConfig } from "../src/types.js";

const originalFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = originalFetch;
});

describe("complete", () => {
  it("throws without calling fetch when a key-requiring provider has no key", async () => {
    const fetchMock = vi.fn();
    globalThis.fetch = fetchMock as unknown as typeof fetch;
    const cfg: AgentConfig = { provider: "openai", apiKey: "", model: "gpt-4o-mini", ollamaUrl: "" };

    await expect(complete(cfg, "hi")).rejects.toThrow("API key is not configured");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("ollama needs no key", async () => {
    globalThis.fetch = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ message: { content: "hi" } }))) as unknown as typeof fetch;
    const cfg: AgentConfig = { provider: "ollama", apiKey: "", model: "llama3.2", ollamaUrl: "http://localhost:11434" };

    await expect(complete(cfg, "hi")).resolves.toBe("hi");
  });

  it("dispatches to the provider matching cfg.provider", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ choices: [{ message: { content: "hi" } }] })));
    globalThis.fetch = fetchMock as unknown as typeof fetch;
    const cfg: AgentConfig = { provider: "groq", apiKey: "gsk-x", model: "llama-3.1-8b-instant", ollamaUrl: "" };

    await complete(cfg, "hello");
    expect(fetchMock.mock.calls[0]![0]).toContain("groq.com");
  });

  it("accepts a pre-built message list instead of a bare prompt", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ content: [{ text: "hi" }] })));
    globalThis.fetch = fetchMock as unknown as typeof fetch;
    const cfg: AgentConfig = { provider: "anthropic", apiKey: "sk-ant-x", model: "claude-haiku-4-5", ollamaUrl: "" };

    await complete(cfg, [
      { role: "user", content: "a" },
      { role: "assistant", content: "b" },
      { role: "user", content: "c" },
    ]);
    const body = JSON.parse((fetchMock.mock.calls[0]![1] as RequestInit).body as string);
    expect(body.messages).toHaveLength(3);
  });
});

describe("streamComplete", () => {
  it("throws before ever calling fetch when unconfigured", async () => {
    const fetchMock = vi.fn();
    globalThis.fetch = fetchMock as unknown as typeof fetch;
    const cfg: AgentConfig = { provider: "gemini", apiKey: "", model: "gemini-2.0-flash", ollamaUrl: "" };

    await expect(streamComplete(cfg, "hi", { onChunk: () => {} })).rejects.toThrow("API key is not configured");
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("streamChat", () => {
  it("normalises the UI history (user-first, merged) before dispatching", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        new ReadableStream<Uint8Array>({
          start(controller) {
            controller.enqueue(
              new TextEncoder().encode('data: {"candidates":[{"content":{"parts":[{"text":"hi"}]}}]}\n\n'),
            );
            controller.close();
          },
        }),
      ),
    );
    globalThis.fetch = fetchMock as unknown as typeof fetch;
    const cfg: AgentConfig = { provider: "gemini", apiKey: "AIza-x", model: "gemini-2.0-flash", ollamaUrl: "" };

    const chunks: string[] = [];
    // Starts with an assistant turn — streamChat must prepend a filler user
    // turn (via buildMessages) before this ever reaches the provider, since
    // Gemini requires user-first ordering.
    await streamChat(cfg, [{ role: "assistant", content: "welcome" }], { onChunk: (c) => chunks.push(c) });

    const body = JSON.parse((fetchMock.mock.calls[0]![1] as RequestInit).body as string);
    expect(body.contents[0]).toEqual({ role: "user", parts: [{ text: "begin" }] });
    expect(chunks).toEqual(["hi"]);
  });
});
