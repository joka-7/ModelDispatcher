import { describe, expect, it } from "vitest";

import {
  clearConfig,
  isConfigReady,
  isProviderConfigured,
  loadConfig,
  saveConfig,
  type ConfigStorage,
} from "../src/config.js";
import type { AgentConfig } from "../src/types.js";

function memoryStorage(initial: Record<string, string> = {}): ConfigStorage {
  const data = new Map(Object.entries(initial));
  return {
    getItem: (key) => data.get(key) ?? null,
    setItem: (key, value) => void data.set(key, value),
    removeItem: (key) => void data.delete(key),
  };
}

describe("loadConfig", () => {
  it("returns an empty provider list with the default Ollama URL when nothing is stored", () => {
    const cfg = loadConfig(memoryStorage());
    expect(cfg).toEqual({ providers: [], ollamaUrl: "http://localhost:11434" });
  });

  it("returns an empty config for corrupt JSON rather than throwing", () => {
    const cfg = loadConfig(memoryStorage({ aiConfig: "{not json" }));
    expect(cfg.providers).toEqual([]);
  });

  it("reads back a stored multi-provider config", () => {
    const stored: AgentConfig = {
      providers: [
        { provider: "anthropic", model: "claude-haiku-4-5", apiKeys: ["sk-ant-a", "sk-ant-b"] },
        { provider: "ollama", model: "llama3.2", apiKeys: [] },
      ],
      ollamaUrl: "http://localhost:11434",
    };
    const cfg = loadConfig(memoryStorage({ aiConfig: JSON.stringify(stored) }));
    expect(cfg).toEqual(stored);
  });

  it("drops an entry with an unrecognised provider id rather than failing the whole load", () => {
    const raw = {
      providers: [
        { provider: "not-a-real-vendor", model: "x", apiKeys: ["k"] },
        { provider: "groq", model: "llama-3.1-8b-instant", apiKeys: ["gsk-x"] },
      ],
      ollamaUrl: "http://localhost:11434",
    };
    const cfg = loadConfig(memoryStorage({ aiConfig: JSON.stringify(raw) }));
    expect(cfg.providers).toEqual([{ provider: "groq", model: "llama-3.1-8b-instant", apiKeys: ["gsk-x"] }]);
  });

  it("falls back to the provider's default model when the stored model is missing", () => {
    const raw = { providers: [{ provider: "gemini", apiKeys: ["k"] }], ollamaUrl: "" };
    const cfg = loadConfig(memoryStorage({ aiConfig: JSON.stringify(raw) }));
    expect(cfg.providers[0]?.model).toBe("gemini-2.0-flash");
  });
});

describe("saveConfig / clearConfig", () => {
  it("persists the full config as JSON, trimming keys and dropping blanks", () => {
    const storage = memoryStorage();
    saveConfig(
      { providers: [{ provider: "openai", model: " gpt-4o-mini ", apiKeys: ["  sk-a  ", "", "sk-b"] }], ollamaUrl: "" },
      storage,
    );
    expect(JSON.parse(storage.getItem("aiConfig")!)).toEqual({
      providers: [{ provider: "openai", model: "gpt-4o-mini", apiKeys: ["sk-a", "sk-b"] }],
      ollamaUrl: "http://localhost:11434",
    });
  });

  it("clearConfig removes the stored blob", () => {
    const storage = memoryStorage({ aiConfig: "{}" });
    clearConfig(storage);
    expect(storage.getItem("aiConfig")).toBeNull();
  });
});

describe("isConfigReady", () => {
  it("false with no providers configured", () => {
    expect(isConfigReady({ providers: [], ollamaUrl: "" })).toBe(false);
  });

  it("false when the only configured provider has no keys", () => {
    expect(isConfigReady({ providers: [{ provider: "openai", model: "m", apiKeys: [] }], ollamaUrl: "" })).toBe(false);
  });

  it("true when ollama is configured, regardless of keys", () => {
    expect(isConfigReady({ providers: [{ provider: "ollama", model: "m", apiKeys: [] }], ollamaUrl: "u" })).toBe(true);
  });

  it("true when at least one configured provider has a key", () => {
    expect(isConfigReady({ providers: [{ provider: "openai", model: "m", apiKeys: ["sk-x"] }], ollamaUrl: "" })).toBe(
      true,
    );
  });
});

describe("isProviderConfigured", () => {
  const cfg: AgentConfig = { providers: [{ provider: "groq", model: "m", apiKeys: ["k"] }], ollamaUrl: "" };

  it("true for a provider already in the list", () => {
    expect(isProviderConfigured(cfg, "groq")).toBe(true);
  });

  it("false for a provider not yet added", () => {
    expect(isProviderConfigured(cfg, "openai")).toBe(false);
  });
});
