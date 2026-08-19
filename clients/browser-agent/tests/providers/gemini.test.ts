import { afterEach, describe, expect, it, vi } from "vitest";

import { completeGemini, streamGemini } from "../../src/providers/gemini.js";
import type { AgentConfig } from "../../src/types.js";

const cfg: AgentConfig = { provider: "gemini", apiKey: "AIza-x", model: "gemini-2.0-flash", ollamaUrl: "" };

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
