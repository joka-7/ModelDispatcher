import { describe, expect, it } from "vitest";

import {
  DEFAULT_EXTERNAL_CHAT_FAVORITE_KEY,
  loadExternalChatFavorite,
  saveExternalChatFavorite,
} from "../src/externalChatFavorite.js";
import type { ConfigStorage } from "../src/config.js";

function memoryStorage(initial: Record<string, string> = {}): ConfigStorage {
  const data = new Map(Object.entries(initial));
  return {
    getItem: (key) => data.get(key) ?? null,
    setItem: (key, value) => void data.set(key, value),
    removeItem: (key) => void data.delete(key),
  };
}

describe("loadExternalChatFavorite", () => {
  it("returns null when nothing is stored", () => {
    expect(loadExternalChatFavorite(memoryStorage())).toBeNull();
  });

  it("returns null for a stored value that isn't a known provider", () => {
    const storage = memoryStorage({ [DEFAULT_EXTERNAL_CHAT_FAVORITE_KEY]: "not-a-real-provider" });
    expect(loadExternalChatFavorite(storage)).toBeNull();
  });

  it("returns the stored favorite when it's a known provider", () => {
    const storage = memoryStorage({ [DEFAULT_EXTERNAL_CHAT_FAVORITE_KEY]: "claude" });
    expect(loadExternalChatFavorite(storage)).toBe("claude");
  });

  it("reads from a custom key", () => {
    const storage = memoryStorage({ myKey: "chatgpt" });
    expect(loadExternalChatFavorite(storage, "myKey")).toBe("chatgpt");
  });
});

describe("saveExternalChatFavorite", () => {
  it("writes the favorite under the default key", () => {
    const storage = memoryStorage();
    saveExternalChatFavorite("gemini", storage);
    expect(storage.getItem(DEFAULT_EXTERNAL_CHAT_FAVORITE_KEY)).toBe("gemini");
  });

  it("removes the key when saving null", () => {
    const storage = memoryStorage({ [DEFAULT_EXTERNAL_CHAT_FAVORITE_KEY]: "groq" });
    saveExternalChatFavorite(null, storage);
    expect(storage.getItem(DEFAULT_EXTERNAL_CHAT_FAVORITE_KEY)).toBeNull();
  });

  it("round-trips through loadExternalChatFavorite", () => {
    const storage = memoryStorage();
    saveExternalChatFavorite("chatgpt", storage);
    expect(loadExternalChatFavorite(storage)).toBe("chatgpt");
  });
});
