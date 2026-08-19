/**
 * Anthropic Claude — direct browser call via raw fetch, no SDK dependency.
 * `anthropic-dangerous-direct-browser-access` is the header the official SDK
 * sends under `dangerouslyAllowBrowser` — acceptable here because the user
 * supplies their own key on their own machine; there is no backend to hide
 * it behind in the first place.
 */

import { consumeLines, describeHttpError, fetchWithRetry } from "../http.js";
import type { AgentConfig, ChatMessage, RequestOptions } from "../types.js";

const DEFAULT_MAX_TOKENS = 1024;
const ANTHROPIC_URL = "https://api.anthropic.com/v1/messages";

function toApiMessages(messages: readonly ChatMessage[]) {
  return messages.filter((m) => m.role !== "system").map((m) => ({ role: m.role, content: m.content }));
}

function systemOf(messages: readonly ChatMessage[], explicit?: string): string | undefined {
  return explicit ?? messages.find((m) => m.role === "system")?.content;
}

function buildBody(cfg: AgentConfig, messages: readonly ChatMessage[], options: RequestOptions, stream: boolean) {
  const system = systemOf(messages, options.systemInstruction);
  return {
    model: cfg.model,
    max_tokens: options.maxTokens ?? DEFAULT_MAX_TOKENS,
    ...(system ? { system } : {}),
    messages: toApiMessages(messages),
    ...(stream ? { stream: true } : {}),
  };
}

function headers(cfg: AgentConfig): HeadersInit {
  return {
    "Content-Type": "application/json",
    "x-api-key": cfg.apiKey,
    "anthropic-version": "2023-06-01",
    "anthropic-dangerous-direct-browser-access": "true",
  };
}

export async function completeAnthropic(
  cfg: AgentConfig,
  messages: readonly ChatMessage[],
  options: RequestOptions = {},
): Promise<string> {
  const res = await fetchWithRetry(
    ANTHROPIC_URL,
    { method: "POST", headers: headers(cfg), body: JSON.stringify(buildBody(cfg, messages, options, false)) },
    options.signal,
  );
  if (!res.ok) throw new Error(await describeHttpError(res));
  const data = await res.json();
  return data.content?.[0]?.text ?? "";
}

export async function streamAnthropic(
  cfg: AgentConfig,
  messages: readonly ChatMessage[],
  onChunk: (fullTextSoFar: string) => void,
  options: RequestOptions = {},
): Promise<string> {
  const res = await fetchWithRetry(
    ANTHROPIC_URL,
    { method: "POST", headers: headers(cfg), body: JSON.stringify(buildBody(cfg, messages, options, true)) },
    options.signal,
  );
  if (!res.ok) throw new Error(await describeHttpError(res));

  let full = "";
  await consumeLines(res, (line) => {
    if (!line.startsWith("data: ")) return;
    const raw = line.slice(6).trim();
    try {
      const event = JSON.parse(raw);
      if (event.type === "content_block_delta" && event.delta?.type === "text_delta") {
        full += event.delta.text;
        onChunk(full);
      }
    } catch {
      // Skip a malformed/partial SSE frame.
    }
  });
  return full;
}
