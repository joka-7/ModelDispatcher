import { describe, expect, it, vi } from "vitest";

import { EXTERNAL_CHAT_PROVIDERS, openExternalChat } from "../src/externalChat.js";

function fakeClipboard(opts: { fails?: boolean } = {}) {
  const writeText = opts.fails
    ? vi.fn().mockRejectedValue(new Error("denied"))
    : vi.fn().mockResolvedValue(undefined);
  return { writeText };
}

describe("EXTERNAL_CHAT_PROVIDERS", () => {
  it("covers exactly chatgpt, claude, gemini, and groq", () => {
    expect(Object.keys(EXTERNAL_CHAT_PROVIDERS).sort()).toEqual([
      "chatgpt",
      "claude",
      "gemini",
      "groq",
    ]);
  });

  it("every homeUrl is a real https URL", () => {
    for (const info of Object.values(EXTERNAL_CHAT_PROVIDERS)) {
      expect(info.homeUrl).toMatch(/^https:\/\//);
    }
  });
});

describe("openExternalChat", () => {
  it("embeds the question in the URL for a provider with a known prefill parameter", async () => {
    const open = vi.fn();
    const result = await openExternalChat("claude", "how do closures work?", {
      open,
      clipboard: fakeClipboard(),
    });

    expect(result.prefilled).toBe(true);
    expect(result.url).toContain("claude.ai/new?");
    expect(new URL(result.url).searchParams.get("q")).toBe("how do closures work?");
    expect(open).toHaveBeenCalledWith(result.url);
  });

  it("falls back to the plain homepage for a provider with no known prefill parameter", async () => {
    const open = vi.fn();
    const result = await openExternalChat("groq", "explain recursion", {
      open,
      clipboard: fakeClipboard(),
    });

    expect(result.prefilled).toBe(false);
    expect(result.url).toBe(EXTERNAL_CHAT_PROVIDERS.groq.homeUrl);
    expect(open).toHaveBeenCalledWith(result.url);
  });

  it("always copies the question to the clipboard, regardless of prefill support", async () => {
    const clipboard = fakeClipboard();
    await openExternalChat("groq", "no prefill for this one", { open: vi.fn(), clipboard });

    expect(clipboard.writeText).toHaveBeenCalledWith("no prefill for this one");
  });

  it("reports copiedToClipboard: false without throwing when the clipboard write fails", async () => {
    const result = await openExternalChat("chatgpt", "hello", {
      open: vi.fn(),
      clipboard: fakeClipboard({ fails: true }),
    });

    expect(result.copiedToClipboard).toBe(false);
  });

  it("reports copiedToClipboard: false without throwing when no clipboard is available at all", async () => {
    const result = await openExternalChat("chatgpt", "hello", { open: vi.fn() });

    expect(result.copiedToClipboard).toBe(false);
  });

  it("still opens the tab even when the clipboard is unavailable", async () => {
    const open = vi.fn();
    await openExternalChat("gemini", "hi", { open });

    expect(open).toHaveBeenCalledTimes(1);
  });

  it("gemini opens Google Search's AI Mode (udm=50), not gemini.google.com", async () => {
    const result = await openExternalChat("gemini", "what's the weather model?", {
      open: vi.fn(),
      clipboard: fakeClipboard(),
    });

    expect(result.url).toContain("google.com/search?");
    expect(result.url).toContain("udm=50");
  });

  it("URL-encodes special characters in the question", async () => {
    const result = await openExternalChat("chatgpt", "a & b = c?", {
      open: vi.fn(),
      clipboard: fakeClipboard(),
    });

    expect(result.url).not.toContain("a & b = c?");
    expect(new URL(result.url).searchParams.get("q")).toBe("a & b = c?");
  });
});
