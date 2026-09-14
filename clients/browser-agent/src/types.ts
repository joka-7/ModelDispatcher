/**
 * Shared vocabulary for the browser agent.
 *
 * Mirrors the split model-dispatcher's Python core uses: plain, dependency-free
 * value types here, behaviour in `providers/*` and `agent.ts`.
 */

export type ProviderId = "gemini" | "openai" | "anthropic" | "groq" | "ollama";

/** Static metadata about a provider — enough to render a settings picker. */
export interface ProviderInfo {
  readonly id: ProviderId;
  readonly name: string;
  /** Whether this provider has a genuinely free tier (not just "has a trial"). */
  readonly free: boolean;
  /** True for providers that need no API key at all (e.g. a local Ollama). */
  readonly noKey?: boolean;
  readonly defaultModel: string;
  /** UI placeholder text for the key input (e.g. "sk-ant-..."). */
  readonly placeholder: string;
  readonly infoUrl: string;
  readonly infoText: string;
}

/**
 * One configured vendor: its model, and the key(s) pooled for it. More than
 * one key is tried in order (e.g. a personal key and a team key) before
 * this vendor is considered exhausted and the dispatcher moves to the next
 * configured provider. Ignored for `provider: "ollama"`, which authenticates
 * via `AgentConfig.ollamaUrl` instead of a key.
 */
export interface ProviderCredential {
  readonly provider: ProviderId;
  readonly model: string;
  readonly apiKeys: readonly string[];
}

/**
 * The full BYOK configuration: an ordered fallback list of vendors (each
 * with its own pooled keys) to try in turn, plus Ollama's local server URL
 * (shared across the whole config — there's only one local Ollama, not one
 * per fallback slot). `dispatch`/`complete`/`streamComplete` walk this list
 * candidate by candidate, mirroring the Python core's fallback chain.
 */
export interface AgentConfig {
  readonly providers: readonly ProviderCredential[];
  readonly ollamaUrl: string;
}

/**
 * One concrete attempt: a specific vendor, model, and (for keyed vendors) a
 * single already-resolved key — what an individual `providers/*` module
 * needs to make one call. Distinct from `AgentConfig`, which holds the whole
 * configured fallback list before the dispatch loop has picked a candidate.
 */
export interface ProviderCallConfig {
  readonly provider: ProviderId;
  readonly model: string;
  readonly apiKey: string;
  readonly ollamaUrl: string;
}

export type ChatRole = "system" | "user" | "assistant";

export interface ChatMessage {
  readonly role: ChatRole;
  readonly content: string;
}

/** Options shared by both complete() and streamComplete()/streamChat(). */
export interface RequestOptions {
  /** System prompt / instruction, applied via each provider's native mechanism. */
  systemInstruction?: string;
  /** Request the provider's structured-JSON response mode where it has one
   * (OpenAI-compatible providers only — Gemini's `responseMimeType` is
   * always requested by callers that need it via a raw prompt instruction,
   * Anthropic and Ollama have no such mode). */
  jsonMode?: boolean;
  maxTokens?: number;
  /** Cancel the request (e.g. component unmount). Independent of, and
   * merged with, the library's own request timeout. */
  signal?: AbortSignal;
}

export interface StreamOptions extends RequestOptions {
  /** Called with the *cumulative* text so far after every chunk, matching
   * every existing app's streaming callback shape. */
  onChunk: (fullTextSoFar: string) => void;
}

/** A free, public AI chat web product `openExternalChat` can hand a question
 * off to — the no-API-key escape hatch, distinct from the `ProviderId`s above
 * (which all require a BYOK credential). */
export type ExternalChatProviderId = "chatgpt" | "claude" | "gemini" | "groq";

/** Static metadata about one external chat provider. */
export interface ExternalChatProviderInfo {
  readonly id: ExternalChatProviderId;
  readonly name: string;
  /** Where `openExternalChat` sends the user when there's no known
   * query-prefill parameter for this provider (or as the base URL the
   * parameter is appended to). */
  readonly homeUrl: string;
  /** Build the deep-link URL for a given question, when this provider has a
   * known (unofficial, reverse-engineered) prefill parameter. `null` when it
   * doesn't — `openExternalChat` falls back to `homeUrl` plus the clipboard. */
  readonly buildUrl: ((question: string) => string) | null;
}
