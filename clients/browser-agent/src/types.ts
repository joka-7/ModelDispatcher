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

/** The active provider/key/model selection — one at a time, BYOK. */
export interface AgentConfig {
  readonly provider: ProviderId;
  readonly apiKey: string;
  readonly model: string;
  /** Only meaningful when provider is "ollama"; ignored otherwise. */
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
