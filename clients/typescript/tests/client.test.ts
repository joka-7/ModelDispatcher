import { describe, expect, it, vi } from "vitest";

import { GatewayClient } from "../src/client.js";
import type { HandoffEvent } from "../src/events.js";
import type { Scheduler } from "../src/types.js";

/** Scheduler that never actually waits, so backoff tests run instantly. */
const INSTANT: Scheduler = { sleep: async () => {}, now: () => 0 };

/** A `fetch` stub returning canned responses in sequence, counting calls. */
function sequenceFetch(responses: Array<() => Response>): {
  fetchImpl: typeof fetch;
  calls: () => number;
} {
  let i = 0;
  const fetchImpl = (async () => {
    const factory = responses[Math.min(i, responses.length - 1)];
    i += 1;
    return factory!();
  }) as unknown as typeof fetch;
  return { fetchImpl, calls: () => i };
}

const json = (status: number, body: unknown) => () =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });

describe("GatewayClient retry/backoff", () => {
  it("(a) retries 5xx and succeeds — 3×500 then 200", async () => {
    const { fetchImpl, calls } = sequenceFetch([
      json(503, { error: "all_providers_exhausted" }),
      json(503, { error: "all_providers_exhausted" }),
      json(500, { error: "internal_error" }),
      json(200, { final: "done", stop_reason: "stop", complexity: "TRIVIAL" }),
    ]);
    const client = new GatewayClient({
      fetchImpl,
      retry: { scheduler: INSTANT, random: () => 0 },
    });

    const outcome = await client.dispatch({ prompt: "hi" });

    expect(outcome.kind).toBe("ok");
    expect(calls()).toBe(4); // 1 initial + 3 retries
  });

  it("(d) never retries a 402/429 handoff", async () => {
    const { fetchImpl, calls } = sequenceFetch([
      json(402, {
        error: "quota_exceeded",
        provider: "openai",
        action: "trigger_key_wizard",
      }),
    ]);
    const client = new GatewayClient({
      fetchImpl,
      retry: { scheduler: INSTANT },
    });

    const outcome = await client.dispatch({ prompt: "hi" });

    expect(outcome.kind).toBe("handoff");
    expect(calls()).toBe(1);
  });
});

describe("GatewayClient handoff decoding", () => {
  it("(b) decodes trigger_key_wizard and publishes to the bus", async () => {
    const { fetchImpl } = sequenceFetch([
      json(429, {
        error: "quota_exceeded",
        provider: "anthropic",
        action: "trigger_key_wizard",
        detail: "free tier spent",
      }),
    ]);
    const client = new GatewayClient({ fetchImpl });
    const events: HandoffEvent[] = [];
    client.bus.on("handoff", (e) => events.push(e));

    const outcome = await client.dispatch({ prompt: "hi" });

    expect(outcome.kind).toBe("handoff");
    if (outcome.kind !== "handoff") throw new Error("unreachable");
    expect(outcome.status).toBe(429);
    expect(outcome.handoff.provider).toBe("anthropic");
    expect(outcome.handoff.action).toBe("trigger_key_wizard");
    expect(events).toHaveLength(1);
    expect(events[0]!.handoff.detail).toBe("free tier spent");
  });

  it("maps a non-handoff error body to kind:error", async () => {
    const { fetchImpl } = sequenceFetch([
      json(403, { error: "perimeter_violation", detail: "bad tenant" }),
    ]);
    const client = new GatewayClient({ fetchImpl, retry: { scheduler: INSTANT } });

    const outcome = await client.dispatch({ prompt: "hi" });

    expect(outcome.kind).toBe("error");
    if (outcome.kind !== "error") throw new Error("unreachable");
    expect(outcome.status).toBe(403);
    expect(outcome.error.error).toBe("perimeter_violation");
  });
});

describe("GatewayClient transport failures", () => {
  it("(c) maps a timeout to kind:network/timeout", async () => {
    // A fetch that only settles when its signal aborts.
    const hangingFetch = ((_url: string, init?: RequestInit) =>
      new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () =>
          reject(new DOMException("aborted", "AbortError")),
        );
      })) as unknown as typeof fetch;

    const client = new GatewayClient({
      fetchImpl: hangingFetch,
      timeoutMs: 20,
      retry: { scheduler: INSTANT },
    });

    const outcome = await client.dispatch({ prompt: "hi" });

    expect(outcome.kind).toBe("network");
    if (outcome.kind !== "network") throw new Error("unreachable");
    expect(outcome.error.kind).toBe("timeout");
  });

  it("maps a fetch TypeError (offline) to kind:network/offline", async () => {
    const offlineFetch = (async () => {
      throw new TypeError("Failed to fetch");
    }) as unknown as typeof fetch;
    const client = new GatewayClient({
      fetchImpl: offlineFetch,
      retry: { scheduler: INSTANT },
    });

    const outcome = await client.dispatch({ prompt: "hi" });

    expect(outcome.kind).toBe("network");
    if (outcome.kind !== "network") throw new Error("unreachable");
    expect(outcome.error.kind).toBe("offline");
  });
});

describe("GatewayClient App Check", () => {
  it("attaches the X-Firebase-AppCheck header from the provider", async () => {
    const seen = vi.fn();
    const capturingFetch = ((_url: string, init?: RequestInit) => {
      seen(init?.headers);
      return Promise.resolve(new Response("{}", { status: 200 }));
    }) as unknown as typeof fetch;

    const client = new GatewayClient({
      fetchImpl: capturingFetch,
      appCheckTokenProvider: async () => "attestation-token",
    });
    await client.dispatch({ prompt: "hi" });

    expect(seen).toHaveBeenCalledOnce();
    const headers = seen.mock.calls[0]![0] as Record<string, string>;
    expect(headers["X-Firebase-AppCheck"]).toBe("attestation-token");
  });
});
