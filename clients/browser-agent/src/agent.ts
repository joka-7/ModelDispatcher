/**
 * The public entry points. Three functions cover every call shape the four
 * apps this was extracted from actually used:
 *
 *   - complete()       — one-shot prompt in, full text back (HighFive, StepByLearn)
 *   - streamComplete()  — one-shot prompt in, incremental text via onChunk (JobFlowTracker's runStream)
 *   - streamChat()      — a UI chat history in (auto-normalised via buildMessages), incremental text back (JobFlowTracker's/KanDOne's streamChat)
 *
 * All three dispatch on `cfg.provider` to the matching provider module;
 * callers never need their own provider switch statement.
 */

import { buildMessages, type BuildMessagesOptions } from "./messages.js";
import { completeAnthropic, streamAnthropic } from "./providers/anthropic.js";
import { completeGemini, streamGemini } from "./providers/gemini.js";
import { completeOllama, streamOllama } from "./providers/ollama.js";
import { completeOpenAICompatible, streamOpenAICompatible } from "./providers/openaiCompatible.js";
import type { AgentConfig, ChatMessage, RequestOptions, StreamOptions } from "./types.js";

function assertReady(cfg: AgentConfig): void {
  if (cfg.provider !== "ollama" && !cfg.apiKey) {
    throw new Error("API key is not configured");
  }
}

/** Non-streaming completion. `prompt` is wrapped as a single user turn;
 * pass `messages` instead for an already-built multi-turn history. */
export async function complete(
  cfg: AgentConfig,
  promptOrMessages: string | readonly ChatMessage[],
  options: RequestOptions = {},
): Promise<string> {
  assertReady(cfg);
  const messages: readonly ChatMessage[] =
    typeof promptOrMessages === "string" ? [{ role: "user", content: promptOrMessages }] : promptOrMessages;

  switch (cfg.provider) {
    case "gemini":
      return completeGemini(cfg, messages, options);
    case "anthropic":
      return completeAnthropic(cfg, messages, options);
    case "ollama":
      return completeOllama(cfg, messages, options);
    case "openai":
    case "groq":
      return completeOpenAICompatible(cfg.provider, cfg, messages, options);
  }
}

/** Streaming completion. `prompt` is wrapped as a single user turn; pass
 * `messages` instead for an already-built multi-turn history. */
export async function streamComplete(
  cfg: AgentConfig,
  promptOrMessages: string | readonly ChatMessage[],
  options: StreamOptions,
): Promise<string> {
  assertReady(cfg);
  const messages: readonly ChatMessage[] =
    typeof promptOrMessages === "string" ? [{ role: "user", content: promptOrMessages }] : promptOrMessages;
  const { onChunk, ...rest } = options;

  switch (cfg.provider) {
    case "gemini":
      return streamGemini(cfg, messages, onChunk, rest);
    case "anthropic":
      return streamAnthropic(cfg, messages, onChunk, rest);
    case "ollama":
      return streamOllama(cfg, messages, onChunk, rest);
    case "openai":
    case "groq":
      return streamOpenAICompatible(cfg.provider, cfg, messages, onChunk, rest);
  }
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
