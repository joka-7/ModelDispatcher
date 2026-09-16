import { afterEach, describe, expect, it, vi } from "vitest";

import {
  AllProvidersExhaustedError,
  complete,
  NoProviderConfiguredError,
  streamChat,
  streamComplete,
} from "../src/agent.js";
import type { AgentConfig } from "../src/types.js";

const originalFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = originalFetch;
});

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

describe("complete", () => {
  it("throws NoProviderConfiguredError without calling fetch when nothing is configured", async () => {
    const fetchMock = vi.fn();
    globalThis.fetch = fetchMock as unknown as typeof fetch;
    const cfg: AgentConfig = { providers: [], ollamaUrl: "" };

    await expect(complete(cfg, "hi")).rejects.toThrow(NoProviderConfiguredError);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("throws NoProviderConfiguredError when a keyed provider is configured with no keys", async () => {
    const fetchMock = vi.fn();
    globalThis.fetch = fetchMock as unknown as typeof fetch;
    const cfg: AgentConfig = { providers: [{ provider: "openai", model: "gpt-4o-mini", apiKeys: [] }], ollamaUrl: "" };

    await expect(complete(cfg, "hi")).rejects.toThrow(NoProviderConfiguredError);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("ollama needs no key", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(jsonResponse({ message: { content: "hi" } })) as unknown as typeof fetch;
    const cfg: AgentConfig = {
      providers: [{ provider: "ollama", model: "llama3.2", apiKeys: [] }],
      ollamaUrl: "http://localhost:11434",
    };

    await expect(complete(cfg, "hi")).resolves.toBe("hi");
  });

  it("dispatches to the configured provider", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ choices: [{ message: { content: "hi" } }] }));
    globalThis.fetch = fetchMock as unknown as typeof fetch;
    const cfg: AgentConfig = {
      providers: [{ provider: "groq", model: "llama-3.1-8b-instant", apiKeys: ["gsk-x"] }],
      ollamaUrl: "",
    };

    await complete(cfg, "hello");
    expect(fetchMock.mock.calls[0]![0]).toContain("groq.com");
  });

  it("accepts a pre-built message list instead of a bare prompt", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ content: [{ text: "hi" }] }));
    globalThis.fetch = fetchMock as unknown as typeof fetch;
    const cfg: AgentConfig = {
      providers: [{ provider: "anthropic", model: "claude-haiku-4-5", apiKeys: ["sk-ant-x"] }],
      ollamaUrl: "",
    };

    await complete(cfg, [
      { role: "user", content: "a" },
      { role: "assistant", content: "b" },
      { role: "user", content: "c" },
    ]);
    const body = JSON.parse((fetchMock.mock.calls[0]![1] as RequestInit).body as string);
    expect(body.messages).toHaveLength(3);
  });

  it("falls back to the next pooled key for the same provider on failure", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ error: { message: "invalid key" } }, 401))
      .mockResolvedValueOnce(jsonResponse({ choices: [{ message: { content: "hi" } }] }));
    globalThis.fetch = fetchMock as unknown as typeof fetch;
    const cfg: AgentConfig = {
      providers: [{ provider: "openai", model: "gpt-4o-mini", apiKeys: ["bad-key", "good-key"] }],
      ollamaUrl: "",
    };

    // 401 isn't retried within a single attempt (fetchWithRetry only retries
    // 429/5xx), but the second pooled key IS a new candidate the dispatcher
    // tries next.
    await expect(complete(cfg, "hi")).resolves.toBe("hi");
    expect(fetchMock).toHaveBeenCalledTimes(2);
    const secondCallAuth = (fetchMock.mock.calls[1]![1] as RequestInit).headers as Record<string, string>;
    expect(secondCallAuth.Authorization).toBe("Bearer good-key");
  });

  it("falls back to the next configured provider once a provider's keys are exhausted", async () => {
    const fetchMock = vi
      .fn()
      // 400, not 429/5xx: fetchWithRetry's own internal retry (a real
      // 600ms delay) is exercised by http.test.ts already — this test is
      // only about falling through to the next configured provider.
      .mockResolvedValueOnce(jsonResponse({ error: { message: "bad request" } }, 400))
      .mockResolvedValueOnce(jsonResponse({ content: [{ text: "from anthropic" }] }));
    globalThis.fetch = fetchMock as unknown as typeof fetch;
    const cfg: AgentConfig = {
      providers: [
        { provider: "openai", model: "gpt-4o-mini", apiKeys: ["sk-x"] },
        { provider: "anthropic", model: "claude-haiku-4-5", apiKeys: ["sk-ant-x"] },
      ],
      ollamaUrl: "",
    };

    await expect(complete(cfg, "hi")).resolves.toBe("from anthropic");
  });

  it("throws AllProvidersExhaustedError listing every failed attempt when all candidates fail", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(jsonResponse({ error: { message: "down" } }, 400)) as unknown as typeof fetch;
    const cfg: AgentConfig = {
      providers: [
        { provider: "openai", model: "gpt-4o-mini", apiKeys: ["sk-x"] },
        { provider: "anthropic", model: "claude-haiku-4-5", apiKeys: ["sk-ant-x"] },
      ],
      ollamaUrl: "",
    };

    const error = await complete(cfg, "hi").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(AllProvidersExhaustedError);
    expect((error as AllProvidersExhaustedError).attempts).toHaveLength(2);
    expect((error as AllProvidersExhaustedError).attempts.map((a) => a.provider)).toEqual(["openai", "anthropic"]);
  });
});

describe("streamComplete", () => {
  it("throws NoProviderConfiguredError before ever calling fetch when unconfigured", async () => {
    const fetchMock = vi.fn();
    globalThis.fetch = fetchMock as unknown as typeof fetch;
    const cfg: AgentConfig = { providers: [], ollamaUrl: "" };

    await expect(streamComplete(cfg, "hi", { onChunk: () => {} })).rejects.toThrow(NoProviderConfiguredError);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("does not fall back once a candidate has already streamed a chunk", async () => {
    function streamThatEmitsThenFails(): Response {
      return new Response(
        new ReadableStream<Uint8Array>({
          async start(controller) {
            controller.enqueue(new TextEncoder().encode('data: {"choices":[{"delta":{"content":"partial"}}]}\n\n'));
            // Erroring in the same tick as enqueue() discards the queued
            // chunk outright (the stream never leaves it readable) — yield
            // first so the reader's first read() actually resolves with it.
            await new Promise((resolve) => setTimeout(resolve, 0));
            controller.error(new Error("connection dropped"));
          },
        }),
      );
    }
    globalThis.fetch = vi.fn().mockResolvedValue(streamThatEmitsThenFails()) as unknown as typeof fetch;
    const cfg: AgentConfig = {
      providers: [
        { provider: "openai", model: "gpt-4o-mini", apiKeys: ["sk-x"] },
        { provider: "anthropic", model: "claude-haiku-4-5", apiKeys: ["sk-ant-x"] },
      ],
      ollamaUrl: "",
    };

    const chunks: string[] = [];
    await expect(
      streamComplete(cfg, "hi", { onChunk: (c) => chunks.push(c) }),
    ).rejects.toThrow("connection dropped");
    expect(chunks).toEqual(["partial"]);
    expect(globalThis.fetch).toHaveBeenCalledTimes(1); // never tried anthropic — a chunk already reached the caller
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
    const cfg: AgentConfig = {
      providers: [{ provider: "gemini", model: "gemini-2.0-flash", apiKeys: ["AIza-x"] }],
      ollamaUrl: "",
    };

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
