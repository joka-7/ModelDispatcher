import { describe, expect, it } from "vitest";

import { GatewayEventBus } from "../src/events.js";
import { backoffDelayMs, DEFAULT_RETRY_POLICY } from "../src/interceptors/retry.js";
import { isHandoffPayload } from "../src/interceptors/handoff.js";

describe("backoffDelayMs", () => {
  const policy = { ...DEFAULT_RETRY_POLICY, jitter: false };

  it("doubles per attempt until capped", () => {
    expect(backoffDelayMs(policy, 0)).toBe(250);
    expect(backoffDelayMs(policy, 1)).toBe(500);
    expect(backoffDelayMs(policy, 2)).toBe(1000);
    expect(backoffDelayMs(policy, 10)).toBe(policy.maxDelayMs); // capped
  });

  it("applies full jitter within [0, capped)", () => {
    const jittered = { ...DEFAULT_RETRY_POLICY, jitter: true };
    expect(backoffDelayMs(jittered, 1, () => 0)).toBe(0);
    expect(backoffDelayMs(jittered, 1, () => 0.999)).toBeLessThan(500);
  });
});

describe("isHandoffPayload", () => {
  it("accepts a well-formed trigger_key_wizard body", () => {
    expect(
      isHandoffPayload({
        error: "quota_exceeded",
        provider: "openai",
        action: "trigger_key_wizard",
      }),
    ).toBe(true);
  });

  it("rejects unknown actions and malformed bodies", () => {
    expect(isHandoffPayload({ error: "x", provider: "p", action: "boom" })).toBe(false);
    expect(isHandoffPayload({ detail: "no action" })).toBe(false);
    expect(isHandoffPayload(null)).toBe(false);
    expect(isHandoffPayload("nope")).toBe(false);
  });
});

describe("GatewayEventBus", () => {
  it("delivers to subscribers and honours unsubscribe", () => {
    const bus = new GatewayEventBus();
    const seen: number[] = [];
    const off = bus.on("handoff", (e) => seen.push(e.status));

    bus.emit("handoff", {
      status: 402,
      handoff: { error: "quota_exceeded", provider: "openai", action: "trigger_key_wizard" },
    });
    off();
    bus.emit("handoff", {
      status: 429,
      handoff: { error: "quota_exceeded", provider: "openai", action: "trigger_key_wizard" },
    });

    expect(seen).toEqual([402]);
  });

  it("isolates a throwing listener from the rest", () => {
    const errors: unknown[] = [];
    const bus = new GatewayEventBus((e) => errors.push(e));
    const seen: number[] = [];
    bus.on("handoff", () => {
      throw new Error("bad listener");
    });
    bus.on("handoff", (e) => seen.push(e.status));

    bus.emit("handoff", {
      status: 402,
      handoff: { error: "quota_exceeded", provider: "openai", action: "trigger_key_wizard" },
    });

    expect(seen).toEqual([402]);
    expect(errors).toHaveLength(1);
  });
});
