/**
 * @joka-7/modeldispatcher-browser-agent — public API surface.
 *
 * A browser-native, bring-your-own-key AI agent core: the client-side
 * sibling to `model-dispatcher` for apps with no backend to run the Python
 * gateway on. Talks directly to Gemini/OpenAI/Anthropic/Groq/Ollama from the
 * browser, using whatever key the end user supplies — no vendor SDK, no
 * server, nothing sent anywhere but the provider itself.
 */

export {
  AllProvidersExhaustedError,
  complete,
  NoProviderConfiguredError,
  streamChat,
  streamComplete,
} from "./agent.js";
export {
  clearConfig,
  DEFAULT_CONFIG_KEYS,
  isConfigReady,
  isProviderConfigured,
  loadConfig,
  resolveStorage,
  saveConfig,
} from "./config.js";
export type { ConfigKeys, ConfigStorage } from "./config.js";
export { DEFAULT_TIMEOUT_MS, describeHttpError, validateOllamaUrl } from "./http.js";
export { EXTERNAL_CHAT_PROVIDERS, openExternalChat } from "./externalChat.js";
export type { OpenExternalChatDeps, OpenExternalChatResult } from "./externalChat.js";
export {
  DEFAULT_EXTERNAL_CHAT_FAVORITE_KEY,
  loadExternalChatFavorite,
  saveExternalChatFavorite,
} from "./externalChatFavorite.js";
export { buildMessages } from "./messages.js";
export type { BuildMessagesOptions } from "./messages.js";
export { isKnownProvider, modelOptionsFor, MODEL_OPTIONS, PROVIDERS } from "./registry.js";
export type {
  AgentConfig,
  ChatMessage,
  ChatRole,
  ExternalChatProviderId,
  ExternalChatProviderInfo,
  ProviderCredential,
  ProviderId,
  ProviderInfo,
  RequestOptions,
  StreamOptions,
} from "./types.js";
