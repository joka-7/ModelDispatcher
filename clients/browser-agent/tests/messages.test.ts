import { describe, expect, it } from "vitest";

import { buildMessages } from "../src/messages.js";

describe("buildMessages", () => {
  it("coerces an unknown role to user and drops empty content", () => {
    const out = buildMessages([
      { role: "user", content: "hi" },
      // @ts-expect-error deliberately invalid role, mirroring untrusted UI state
      { role: "bogus", content: "x" },
      { role: "assistant", content: "  " },
    ]);
    expect(out).toEqual([{ role: "user", content: "hi\n\nx" }]);
  });

  it("prepends a filler user turn when history starts with assistant", () => {
    const out = buildMessages([{ role: "assistant", content: "hello!" }]);
    expect(out[0]).toEqual({ role: "user", content: "begin" });
    expect(out[1]).toEqual({ role: "assistant", content: "hello!" });
  });

  it("merges consecutive same-role turns", () => {
    const out = buildMessages([
      { role: "user", content: "a" },
      { role: "user", content: "b" },
      { role: "assistant", content: "c" },
    ]);
    expect(out).toEqual([
      { role: "user", content: "a\n\nb" },
      { role: "assistant", content: "c" },
    ]);
  });

  it("drops a sentinel content marker entirely", () => {
    const out = buildMessages([{ role: "user", content: "__sim__" }], { dropContent: "__sim__" });
    expect(out).toEqual([{ role: "user", content: "begin" }]);
  });

  it("forceTrailingFiller always appends a filler turn after the last assistant turn", () => {
    const out = buildMessages([{ role: "assistant", content: "welcome" }], { forceTrailingFiller: true });
    expect(out).toEqual([
      { role: "assistant", content: "welcome" },
      { role: "user", content: "begin" },
    ]);
  });

  it("forceTrailingFiller merges into a trailing same-role turn like any other merge", () => {
    const out = buildMessages([{ role: "user", content: "hi" }], { forceTrailingFiller: true });
    expect(out).toEqual([{ role: "user", content: "hi\n\nbegin" }]);
  });

  it("caps message length", () => {
    const out = buildMessages([{ role: "user", content: "x".repeat(5000) }]);
    expect(out[0]?.content.length).toBe(4000);
  });

  it("an empty history returns a single filler turn", () => {
    expect(buildMessages([])).toEqual([{ role: "user", content: "begin" }]);
  });

  it("fillerContent overrides the default filler text", () => {
    expect(buildMessages([], { fillerContent: "start" })).toEqual([{ role: "user", content: "start" }]);
  });
});
