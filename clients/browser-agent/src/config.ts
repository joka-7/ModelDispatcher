/**
 * BYOK config persistence: the whole `AgentConfig` (an ordered fallback list
 * of providers, each with its own pooled keys, plus the shared Ollama URL)
 * as one JSON blob under one storage key — simpler than one key per field
 * now that the config is a list rather than a single flat selection, and
 * the key name/storage itself stay overridable so an app can keep its own
 * naming without forking the loader logic.
 */

import { PROVIDERS, isKnownProvider } from "./registry.js";
import type { AgentConfig, ProviderCredential, ProviderId } from "./types.js";

/** Minimal Web Storage shape — matches `localStorage`, injectable for tests
 * or for a non-browser host (e.g. a React Native AsyncStorage shim). */
export interface ConfigStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

export interface ConfigKeys {
  /** Single key holding the whole config as JSON. */
  config: string;
}

export const DEFAULT_CONFIG_KEYS: ConfigKeys = {
  config: "aiConfig",
};

const DEFAULT_OLLAMA_URL = "http://localhost:11434";

/** Resolve an explicit storage, or fall back to `localStorage` in a browser.
 * Shared with {@link ./externalChatFavorite.js} so both persistence modules
 * agree on where "no storage available" should throw. */
export function resolveStorage(storage?: ConfigStorage): ConfigStorage {
  if (storage) return storage;
  if (typeof localStorage !== "undefined") return localStorage;
  throw new Error(
    "No storage available: pass a ConfigStorage explicitly outside a browser.",
  );
}

function sanitizeCredential(raw: unknown): ProviderCredential | null {
  if (typeof raw !== "object" || raw === null) return null;
  const { provider, model, apiKeys } = raw as Record<string, unknown>;
  if (typeof provider !== "string" || !isKnownProvider(provider)) return null;

  const keys = Array.isArray(apiKeys)
    ? apiKeys.filter((k): k is string => typeof k === "string" && k.trim().length > 0).map((k) => k.trim())
    : [];
  const resolvedModel = typeof model === "string" && model.trim() ? model.trim() : PROVIDERS[provider].defaultModel;

  return { provider, model: resolvedModel, apiKeys: keys };
}

/** Read the configured provider fallback list + Ollama URL from storage.
 * A missing, empty, or corrupt blob resolves to an empty provider list
 * (nothing configured yet) rather than throwing — the same "still runs,
 * just answers no-credential" posture the rest of this package uses. */
export function loadConfig(
  storage?: ConfigStorage,
  keys: ConfigKeys = DEFAULT_CONFIG_KEYS,
): AgentConfig {
  const store = resolveStorage(storage);
  const raw = store.getItem(keys.config);
  if (!raw) return { providers: [], ollamaUrl: DEFAULT_OLLAMA_URL };

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return { providers: [], ollamaUrl: DEFAULT_OLLAMA_URL };
  }
  if (typeof parsed !== "object" || parsed === null) return { providers: [], ollamaUrl: DEFAULT_OLLAMA_URL };

  const { providers, ollamaUrl } = parsed as Record<string, unknown>;
  const sanitized = Array.isArray(providers)
    ? providers.map(sanitizeCredential).filter((c): c is ProviderCredential => c !== null)
    : [];
  const resolvedOllamaUrl = typeof ollamaUrl === "string" && ollamaUrl.trim() ? ollamaUrl.trim() : DEFAULT_OLLAMA_URL;

  return { providers: sanitized, ollamaUrl: resolvedOllamaUrl };
}

/** Persist the full config, replacing whatever was stored before — callers
 * (e.g. `ModelPicker`) hold the authoritative in-memory list and pass the
 * whole thing on every change, the same controlled-component pattern the
 * React layer uses. */
export function saveConfig(config: AgentConfig, storage?: ConfigStorage, keys: ConfigKeys = DEFAULT_CONFIG_KEYS): void {
  const store = resolveStorage(storage);
  const cleaned: AgentConfig = {
    providers: config.providers.map((cred) => ({
      provider: cred.provider,
      model: cred.model.trim(),
      apiKeys: cred.apiKeys.map((k) => k.trim()).filter((k) => k.length > 0),
    })),
    ollamaUrl: config.ollamaUrl.trim() || DEFAULT_OLLAMA_URL,
  };
  store.setItem(keys.config, JSON.stringify(cleaned));
}

export function clearConfig(storage?: ConfigStorage, keys: ConfigKeys = DEFAULT_CONFIG_KEYS): void {
  resolveStorage(storage).removeItem(keys.config);
}

/** Whether `cfg` has at least one usable candidate to dispatch to — Ollama
 * (no key needed) or any vendor with at least one pooled key. Mirrors
 * `candidatesOf` in `agent.ts` without needing to import its internals. */
export function isConfigReady(cfg: AgentConfig): boolean {
  return cfg.providers.some((cred) => cred.provider === "ollama" || cred.apiKeys.length > 0);
}

/** True when `provider` isn't already in `cfg.providers` — for an "Add
 * provider" control to only offer vendors not yet configured. */
export function isProviderConfigured(cfg: AgentConfig, provider: ProviderId): boolean {
  return cfg.providers.some((cred) => cred.provider === provider);
}
