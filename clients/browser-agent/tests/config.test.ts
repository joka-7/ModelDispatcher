import { describe, expect, it } from "vitest";

import { clearConfig, isConfigReady, loadConfig, saveConfig, type ConfigStorage } from "../src/config.js";

function memoryStorage(initial: Record<string, string> = {}): ConfigStorage {
  const data = new Map(Object.entries(initial));
  return {
    getItem: (key) => data.get(key) ?? null,
    setItem: (key, value) => void data.set(key, value),
    removeItem: (key) => void data.delete(key),
  };
}

describe("loadConfig", () => {
  it("defaults to gemini with an empty key when nothing is stored", () => {
    const cfg = loadConfig(memoryStorage());
    expect(cfg.provider).toBe("gemini");
    expect(cfg.apiKey).toBe("");
    expect(cfg.model).toBe("gemini-2.0-flash");
  });

  it("falls back to gemini for an unknown stored provider", () => {
    const cfg = loadConfig(memoryStorage({ aiProvider: "not-a-real-provider" }));
    expect(cfg.provider).toBe("gemini");
  });

  it("reads the stored provider/key/model", () => {
    const cfg = loadConfig(memoryStorage({ aiProvider: "anthropic", aiApiKey: "sk-ant-x", aiModel: "claude-x" }));
    expect(cfg).toEqual({
      provider: "anthropic",
      apiKey: "sk-ant-x",
      model: "claude-x",
      ollamaUrl: "http://localhost:11434",
    });
  });

  it("falls back through legacyApiKeys in order when the primary key is unset", () => {
    const storage = memoryStorage({ oldKey1: "", oldKey2: "sk-legacy" });
    const cfg = loadConfig(storage, {
      provider: "aiProvider",
      apiKey: "aiApiKey",
      model: "aiModel",
      ollamaUrl: "ollamaUrl",
      legacyApiKeys: ["oldKey1", "oldKey2"],
    });
    expect(cfg.apiKey).toBe("sk-legacy");
  });
});

describe("saveConfig / clearConfig", () => {
  it("writes only the given fields, trimmed", () => {
    const storage = memoryStorage();
    saveConfig({ apiKey: "  sk-x  " }, storage);
    expect(storage.getItem("aiApiKey")).toBe("sk-x");
    expect(storage.getItem("aiProvider")).toBeNull();
  });

  it("clearConfig removes every managed key", () => {
    const storage = memoryStorage({ aiProvider: "openai", aiApiKey: "sk-x", aiModel: "m", ollamaUrl: "u" });
    clearConfig(storage);
    expect(storage.getItem("aiProvider")).toBeNull();
    expect(storage.getItem("aiApiKey")).toBeNull();
  });
});

describe("isConfigReady", () => {
  it("ollama is always ready regardless of key", () => {
    expect(isConfigReady({ provider: "ollama", apiKey: "", model: "m", ollamaUrl: "u" })).toBe(true);
  });

  it("every other provider needs a non-empty key", () => {
    expect(isConfigReady({ provider: "openai", apiKey: "", model: "m", ollamaUrl: "u" })).toBe(false);
    expect(isConfigReady({ provider: "openai", apiKey: "sk-x", model: "m", ollamaUrl: "u" })).toBe(true);
  });
});
