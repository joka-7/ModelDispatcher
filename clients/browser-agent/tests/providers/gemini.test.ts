import { afterEach, describe, expect, it, vi } from "vitest";

import { completeGemini, completeWithToolsGemini, geminiSchema, streamGemini } from "../../src/providers/gemini.js";
import { history, mockReply, portfolio, quote, sentBody } from "./toolFixtures.js";
import type { ProviderCallConfig } from "../../src/types.js";

const cfg: ProviderCallConfig = { provider: "gemini", apiKey: "AIza-x", model: "gemini-2.0-flash", ollamaUrl: "" };

describe("completeGemini", () => {
  const originalFetch = globalThis.fetch;
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("sends the key as a header and system instruction as a top-level field", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ candidates: [{ content: { parts: [{ text: "hi there" }] } }] }), { status: 200 }),
    );
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const text = await completeGemini(cfg, [{ role: "user", content: "hello" }], { systemInstruction: "be terse" });

    expect(text).toBe("hi there");
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("generateContent");
    expect((init.headers as Record<string, string>)["x-goog-api-key"]).toBe("AIza-x");
    const body = JSON.parse(init.body as string);
    expect(body.systemInstruction).toEqual({ parts: [{ text: "be terse" }] });
    expect(body.contents).toEqual([{ role: "user", parts: [{ text: "hello" }] }]);
  });

  it("maps assistant turns to Gemini's 'model' role", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ candidates: [{ content: { parts: [{ text: "ok" }] } }] })));
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    await completeGemini(cfg, [
      { role: "user", content: "a" },
      { role: "assistant", content: "b" },
    ]);
    const body = JSON.parse((fetchMock.mock.calls[0]![1] as RequestInit).body as string);
    expect(body.contents.map((c: { role: string }) => c.role)).toEqual(["user", "model"]);
  });
});

describe("streamGemini", () => {
  const originalFetch = globalThis.fetch;
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("accumulates text across SSE frames and reports the running total", async () => {
    const sse =
      'data: {"candidates":[{"content":{"parts":[{"text":"Hel"}]}}]}\n\n' +
      'data: {"candidates":[{"content":{"parts":[{"text":"lo"}]}}]}\n\n';
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(sse));
        controller.close();
      },
    });
    globalThis.fetch = vi.fn().mockResolvedValue(new Response(stream, { status: 200 })) as unknown as typeof fetch;

    const chunks: string[] = [];
    const full = await streamGemini(cfg, [{ role: "user", content: "hi" }], (c) => chunks.push(c));

    expect(chunks).toEqual(["Hel", "Hello"]);
    expect(full).toBe("Hello");
  });
});

describe("completeWithToolsGemini", () => {
  const originalFetch = globalThis.fetch;
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  const cfg: ProviderCallConfig = { provider: "gemini", apiKey: "AIza", model: "gemini-2.5-flash", ollamaUrl: "" };

  it("declares functions Gemini accepts and echoes the thought signature", async () => {
    const fetchMock = mockReply({ candidates: [{ content: { parts: [{ text: "190.5" }] } }] });

    await completeWithToolsGemini(cfg, history, [quote, portfolio], {});

    const body = sentBody(fetchMock);
    expect(body["tools"]).toEqual([
      {
        functionDeclarations: [
          {
            name: "get_quote",
            description: "Latest price",
            parameters: { type: "object", properties: { symbol: { type: "string" } }, required: ["symbol"] },
          },
          { name: "get_portfolio", description: "The user's holdings" },
        ],
      },
    ]);
    expect((body["contents"] as unknown[]).slice(1)).toEqual([
      {
        role: "model",
        parts: [
          { text: "Checking." },
          { functionCall: { name: "get_quote", args: { symbol: "AAPL" } }, thoughtSignature: "sig-1" },
          { functionCall: { name: "get_portfolio", args: {} } },
        ],
      },
      {
        role: "user",
        parts: [
          { functionResponse: { name: "get_quote", response: { result: "190.5" } } },
          { functionResponse: { name: "get_portfolio", response: { error: "tool error: locked" } } },
        ],
      },
    ]);
  });

  it("decodes function calls with their signature and no id", async () => {
    mockReply({
      candidates: [
        { content: { parts: [{ functionCall: { name: "get_quote", args: { symbol: "MSFT" } }, thoughtSignature: "sig-2" }] } },
      ],
    });

    const turn = await completeWithToolsGemini(cfg, history.slice(0, 2), [quote], {});

    expect(turn).toEqual({
      text: "",
      toolCalls: [{ id: "", name: "get_quote", arguments: { symbol: "MSFT" }, signature: "sig-2" }],
    });
  });

  it("strips unsupported schema keys at every depth", () => {
    expect(
      geminiSchema({ $schema: "x", type: "object", properties: { a: { type: "object", additionalProperties: true } } }),
    ).toEqual({ type: "object", properties: { a: { type: "object" } } });
  });
});
