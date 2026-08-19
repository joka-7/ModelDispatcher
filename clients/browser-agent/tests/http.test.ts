import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { consumeLines, describeHttpError, fetchWithRetry, validateOllamaUrl } from "../src/http.js";

describe("validateOllamaUrl", () => {
  it("accepts http on localhost/127.0.0.1/::1", () => {
    expect(validateOllamaUrl("http://localhost:11434")).toBe("http://localhost:11434");
    expect(validateOllamaUrl("http://127.0.0.1:11434")).toBe("http://127.0.0.1:11434");
  });

  it("rejects a non-HTTPS remote host", () => {
    expect(() => validateOllamaUrl("http://example.com:11434")).toThrow(/HTTPS/);
  });

  it("accepts HTTPS for a remote host", () => {
    expect(validateOllamaUrl("https://ollama.example.com")).toBe("https://ollama.example.com");
  });

  it("rejects an unparsable URL", () => {
    expect(() => validateOllamaUrl("not a url")).toThrow(/Invalid Ollama URL/);
  });
});

describe("fetchWithRetry", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.useRealTimers();
  });

  it("returns immediately on a non-retryable success", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("ok", { status: 200 }));
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const res = await fetchWithRetry("https://example.com", {});
    expect(res.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("retries exactly once on a 429, then returns whatever the second attempt gives", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response("rate limited", { status: 429 }))
      .mockResolvedValueOnce(new Response("ok", { status: 200 }));
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const promise = fetchWithRetry("https://example.com", {});
    await vi.runAllTimersAsync();
    const res = await promise;

    expect(res.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("does not retry a second failure — returns the second response as-is", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response("", { status: 503 }))
      .mockResolvedValueOnce(new Response("", { status: 503 }));
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const promise = fetchWithRetry("https://example.com", {});
    await vi.runAllTimersAsync();
    const res = await promise;

    expect(res.status).toBe(503);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("does not retry a non-retryable 4xx", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("", { status: 401 }));
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const res = await fetchWithRetry("https://example.com", {});
    expect(res.status).toBe(401);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("retries once on a thrown network error, then propagates a second one", async () => {
    const fetchMock = vi.fn().mockRejectedValueOnce(new Error("network down")).mockRejectedValueOnce(new Error("still down"));
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const promise = fetchWithRetry("https://example.com", {});
    const expectation = expect(promise).rejects.toThrow("still down");
    await vi.runAllTimersAsync();
    await expectation;
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("never retries once the external signal is already aborted", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new DOMException("aborted", "AbortError"));
    globalThis.fetch = fetchMock as unknown as typeof fetch;
    const controller = new AbortController();
    controller.abort();

    await expect(fetchWithRetry("https://example.com", {}, controller.signal)).rejects.toThrow();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe("consumeLines", () => {
  function streamedResponse(chunks: string[]): Response {
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        for (const chunk of chunks) controller.enqueue(new TextEncoder().encode(chunk));
        controller.close();
      },
    });
    return new Response(stream);
  }

  it("splits a stream into complete lines, buffering a trailing partial line", async () => {
    const res = streamedResponse(["line one\nline t", "wo\nline three"]);
    const lines: string[] = [];
    await consumeLines(res, (line) => lines.push(line));
    expect(lines).toEqual(["line one", "line two"]);
  });

  it("throws a clear error for a body-less response", async () => {
    const res = new Response(null, { status: 200 });
    await expect(consumeLines(res, () => {})).rejects.toThrow(/Empty response body/);
  });
});

describe("describeHttpError", () => {
  it("prefers the provider's error.message", async () => {
    const res = new Response(JSON.stringify({ error: { message: "bad key" } }), { status: 401 });
    expect(await describeHttpError(res)).toBe("bad key");
  });

  it("falls back to the HTTP status when the body isn't JSON-shaped", async () => {
    const res = new Response("not json", { status: 502 });
    expect(await describeHttpError(res)).toBe("HTTP 502");
  });
});
