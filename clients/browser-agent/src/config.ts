/**
 * BYOK config persistence. Every app used `localStorage` directly under
 * slightly different key names — this keeps that pattern (no new storage
 * mechanism to migrate to) but makes the key names and the storage itself
 * both overridable, so each app can keep its own naming/legacy fallbacks
 * without forking the loader logic.
 */

import { PROVIDERS, isKnownProvider } from "./registry.js";
import type { AgentConfig, ProviderId } from "./types.js";

/** Minimal Web Storage shape — matches `localStorage`, injectable for tests
 * or for a non-browser host (e.g. a React Native AsyncStorage shim). */
export interface ConfigStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

export interface ConfigKeys {
  provider: string;
  apiKey: string;
  model: string;
  ollamaUrl: string;
  /** Older/alternate localStorage keys to also check for apiKey, in order,
   * if the primary key is unset — e.g. JobFlowTracker's pre-multi-provider
   * `anthropicApiKey`. Never written to, only read as a fallback. */
  legacyApiKeys?: string[];
}

export const DEFAULT_CONFIG_KEYS: ConfigKeys = {
  provider: "aiProvider",
  apiKey: "aiApiKey",
  model: "aiModel",
  ollamaUrl: "ollamaUrl",
};

const DEFAULT_OLLAMA_URL = "http://localhost:11434";

function resolveStorage(storage?: ConfigStorage): ConfigStorage {
  if (storage) return storage;
  if (typeof localStorage !== "undefined") return localStorage;
  throw new Error(
    "No storage available: pass a ConfigStorage explicitly outside a browser.",
  );
}

/** Read the active provider/key/model/ollamaUrl selection from storage. */
export function loadConfig(
  storage?: ConfigStorage,
  keys: ConfigKeys = DEFAULT_CONFIG_KEYS,
): AgentConfig {
  const store = resolveStorage(storage);
  const rawProvider = store.getItem(keys.provider) || "gemini";
  const provider: ProviderId = isKnownProvider(rawProvider) ? rawProvider : "gemini";

  let apiKey = (store.getItem(keys.apiKey) || "").trim();
  if (!apiKey) {
    for (const legacyKey of keys.legacyApiKeys ?? []) {
      apiKey = (store.getItem(legacyKey) || "").trim();
      if (apiKey) break;
    }
  }

  const model = (store.getItem(keys.model) || "").trim() || PROVIDERS[provider].defaultModel;
  const ollamaUrl = (store.getItem(keys.ollamaUrl) || DEFAULT_OLLAMA_URL).trim();

  return { provider, apiKey, model, ollamaUrl };
}

/** Persist a partial config update; only the given fields are written. */
export function saveConfig(
  update: Partial<AgentConfig>,
  storage?: ConfigStorage,
  keys: ConfigKeys = DEFAULT_CONFIG_KEYS,
): void {
  const store = resolveStorage(storage);
  if (update.provider !== undefined) store.setItem(keys.provider, update.provider);
  if (update.apiKey !== undefined) store.setItem(keys.apiKey, update.apiKey.trim());
  if (update.model !== undefined) store.setItem(keys.model, update.model.trim());
  if (update.ollamaUrl !== undefined) store.setItem(keys.ollamaUrl, update.ollamaUrl.trim());
}

export function clearConfig(storage?: ConfigStorage, keys: ConfigKeys = DEFAULT_CONFIG_KEYS): void {
  const store = resolveStorage(storage);
  store.removeItem(keys.provider);
  store.removeItem(keys.apiKey);
  store.removeItem(keys.model);
  store.removeItem(keys.ollamaUrl);
}

/** Whether `cfg` has everything needed to actually make a request. */
export function isConfigReady(cfg: AgentConfig): boolean {
  if (cfg.provider === "ollama") return true;
  return cfg.apiKey.length > 0;
}
