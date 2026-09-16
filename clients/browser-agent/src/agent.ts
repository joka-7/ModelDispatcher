/**
 * The public entry points — now multi-provider: `cfg.providers` is an
 * ordered fallback list (each vendor with one or more pooled keys) instead
 * of a single vendor+key, so a rate limit, bad key, or outage on the first
 * configured provider falls through to the next instead of failing the
 * whole request. Mirrors the Python core's fallback chain, simplified for a
 * browser client with no shared quota/routing state to manage.
 *
 *   - complete()       — one-shot prompt in, full text back (HighFive, StepByLearn)
 *   - streamComplete()  — one-shot prompt in, incremental text via onChunk (JobFlowTracker's runStream)
 *   - streamChat()      — a UI chat history in (auto-normalised via buildMessages), incremental text back (JobFlowTracker's/KanDOne's streamChat)
 *
 * All three dispatch on each candidate's `provider` to the matching
 * provider module; callers never need their own provider switch statement.
 */

import { buildMessages, type BuildMessagesOptions } from "./messages.js";
import { completeAnthropic, streamAnthropic } from "./providers/anthropic.js";
import { completeGemini, streamGemini } from "./providers/gemini.js";
import { completeOllama, streamOllama } from "./providers/ollama.js";
import { completeOpenAICompatible, streamOpenAICompatible } from "./providers/openaiCompatible.js";
import type {
  AgentConfig,
  ChatMessage,
  ProviderCallConfig,
  RequestOptions,
  StreamOptions,
} from "./types.js";

/** One candidate that failed, kept only to compose
 * {@link AllProvidersExhaustedError}'s message. */
interface FailedAttempt {
  readonly provider: string;
  readonly error: string;
}

/** `cfg.providers` has nothing usable at all — no vendor has a pooled key,
 * and Ollama isn't configured either. Raised before any network call, the
 * same way the Python core's `NoProviderAvailableError` is. */
export class NoProviderConfiguredError extends Error {
  constructor() {
    super("No AI provider is configured — add a provider and key (or Ollama) in AI settings.");
    this.name = "NoProviderConfiguredError";
  }
}

/** Every configured provider/key was tried and every one failed. */
export class AllProvidersExhaustedError extends Error {
  readonly attempts: readonly FailedAttempt[];

  constructor(attempts: readonly FailedAttempt[]) {
    super(`All configured AI providers failed: ${attempts.map((a) => `${a.provider} (${a.error})`).join("; ")}`);
    this.name = "AllProvidersExhaustedError";
    this.attempts = attempts;
  }
}

/**
 * Flatten the configured provider list into concrete, single-key attempts,
 * in fallback order: each provider's own pooled keys are tried in the order
 * they were added before moving to the next configured provider. Ollama
 * contributes at most one candidate (it authenticates via `cfg.ollamaUrl`,
 * not a key) and only when its own entry is present in the list — a
 * provider with no usable credential is never offered as a candidate at
 * all, the same rule the Python core's registry-building applies.
 */
function candidatesOf(cfg: AgentConfig): ProviderCallConfig[] {
  const candidates: ProviderCallConfig[] = [];
  for (const cred of cfg.providers) {
    if (cred.provider === "ollama") {
      candidates.push({ provider: "ollama", model: cred.model, apiKey: "", ollamaUrl: cfg.ollamaUrl });
      continue;
    }
    for (const apiKey of cred.apiKeys) {
      if (apiKey) candidates.push({ provider: cred.provider, model: cred.model, apiKey, ollamaUrl: cfg.ollamaUrl });
    }
  }
  return candidates;
}

function messagesOf(promptOrMessages: string | readonly ChatMessage[]): readonly ChatMessage[] {
  return typeof promptOrMessages === "string" ? [{ role: "user", content: promptOrMessages }] : promptOrMessages;
}

function completeOne(
  candidate: ProviderCallConfig,
  messages: readonly ChatMessage[],
  options: RequestOptions,
): Promise<string> {
  switch (candidate.provider) {
    case "gemini":
      return completeGemini(candidate, messages, options);
    case "anthropic":
      return completeAnthropic(candidate, messages, options);
    case "ollama":
      return completeOllama(candidate, messages, options);
    case "openai":
    case "groq":
      return completeOpenAICompatible(candidate.provider, candidate, messages, options);
  }
}

/** Non-streaming completion, tried across every configured provider/key in
 * order until one succeeds. `prompt` is wrapped as a single user turn; pass
 * `messages` instead for an already-built multi-turn history.
 *
 * Raises:
 *   NoProviderConfiguredError: `cfg.providers` has no usable credential at all.
 *   AllProvidersExhaustedError: every candidate was tried and failed;
 *     `.attempts` lists each provider and its error.
 */
export async function complete(
  cfg: AgentConfig,
  promptOrMessages: string | readonly ChatMessage[],
  options: RequestOptions = {},
): Promise<string> {
  const candidates = candidatesOf(cfg);
  if (candidates.length === 0) throw new NoProviderConfiguredError();
  const messages = messagesOf(promptOrMessages);

  const attempts: FailedAttempt[] = [];
  for (const candidate of candidates) {
    try {
      return await completeOne(candidate, messages, options);
    } catch (err) {
      attempts.push({ provider: candidate.provider, error: (err as Error).message });
    }
  }
  throw new AllProvidersExhaustedError(attempts);
}

function streamOne(
  candidate: ProviderCallConfig,
  messages: readonly ChatMessage[],
  onChunk: (fullTextSoFar: string) => void,
  options: RequestOptions,
): Promise<string> {
  switch (candidate.provider) {
    case "gemini":
      return streamGemini(candidate, messages, onChunk, options);
    case "anthropic":
      return streamAnthropic(candidate, messages, onChunk, options);
    case "ollama":
      return streamOllama(candidate, messages, onChunk, options);
    case "openai":
    case "groq":
      return streamOpenAICompatible(candidate.provider, candidate, messages, onChunk, options);
  }
}

/**
 * Streaming completion, tried across every configured provider/key in
 * order — but only up to the first chunk actually streamed. Once any text
 * has reached `onChunk` for a candidate, a later failure on that same
 * candidate is surfaced immediately rather than silently retried on the
 * next provider: the caller has already rendered a partial answer, and
 * switching providers mid-stream would duplicate or contradict it rather
 * than complete it.
 *
 * Raises the same errors as {@link complete}.
 */
export async function streamComplete(
  cfg: AgentConfig,
  promptOrMessages: string | readonly ChatMessage[],
  options: StreamOptions,
): Promise<string> {
  const candidates = candidatesOf(cfg);
  if (candidates.length === 0) throw new NoProviderConfiguredError();
  const messages = messagesOf(promptOrMessages);
  const { onChunk, ...rest } = options;

  const attempts: FailedAttempt[] = [];
  for (const candidate of candidates) {
    let startedStreaming = false;
    try {
      return await streamOne(
        candidate,
        messages,
        (text) => {
          startedStreaming = true;
          onChunk(text);
        },
        rest,
      );
    } catch (err) {
      if (startedStreaming) throw err;
      attempts.push({ provider: candidate.provider, error: (err as Error).message });
    }
  }
  throw new AllProvidersExhaustedError(attempts);
}

/**
 * Streaming multi-turn chat: normalises a raw UI message list via
 * {@link buildMessages} (role validation, alternation, sentinel-dropping)
 * before dispatching — the one thing `streamComplete()` deliberately
 * doesn't do, since its `messages` input is assumed already well-formed.
 */
export async function streamChat(
  cfg: AgentConfig,
  uiMessages: readonly ChatMessage[],
  options: StreamOptions & BuildMessagesOptions,
): Promise<string> {
  const normalised = buildMessages(uiMessages, options);
  return streamComplete(cfg, normalised, options);
}
