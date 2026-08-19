/**
 * Ollama — a local (or self-hosted) model server, no API key. Always uses
 * `/api/chat` (message-list based) rather than switching between `/generate`
 * and `/chat` per call shape — a single-turn prompt is just a one-message
 * chat, so one code path covers both without the caller needing to know
 * which Ollama endpoint that implies.
 */

import { consumeLines, fetchWithRetry, validateOllamaUrl } from "../http.js";
import type { AgentConfig, ChatMessage, RequestOptions } from "../types.js";

const DEFAULT_MAX_TOKENS = 1024;

function toApiMessages(messages: readonly ChatMessage[], systemInstruction?: string) {
  const hasSystemTurn = messages.some((m) => m.role === "system");
  const system = !hasSystemTurn && systemInstruction ? [{ role: "system", content: systemInstruction }] : [];
  return [...system, ...messages.map((m) => ({ role: m.role, content: m.content }))];
}

function buildBody(cfg: AgentConfig, messages: readonly ChatMessage[], options: RequestOptions, stream: boolean) {
  return {
    model: cfg.model,
    messages: toApiMessages(messages, options.systemInstruction),
    stream,
    options: { num_predict: options.maxTokens ?? DEFAULT_MAX_TOKENS },
  };
}

export async function completeOllama(
  cfg: AgentConfig,
  messages: readonly ChatMessage[],
  options: RequestOptions = {},
): Promise<string> {
  const baseUrl = validateOllamaUrl(cfg.ollamaUrl);
  const res = await fetchWithRetry(
    `${baseUrl}/api/chat`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(buildBody(cfg, messages, options, false)),
    },
    options.signal,
  );
  if (!res.ok) throw new Error(`Ollama error: HTTP ${res.status}. Is Ollama running?`);
  const data = await res.json();
  return data.message?.content ?? "";
}

export async function streamOllama(
  cfg: AgentConfig,
  messages: readonly ChatMessage[],
  onChunk: (fullTextSoFar: string) => void,
  options: RequestOptions = {},
): Promise<string> {
  const baseUrl = validateOllamaUrl(cfg.ollamaUrl);
  const res = await fetchWithRetry(
    `${baseUrl}/api/chat`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(buildBody(cfg, messages, options, true)),
    },
    options.signal,
  );
  if (!res.ok) throw new Error(`Ollama error: HTTP ${res.status}. Is Ollama running?`);

  let full = "";
  await consumeLines(res, (line) => {
    if (!line.trim()) return;
    try {
      const text = JSON.parse(line).message?.content;
      if (text) {
        full += text;
        onChunk(full);
      }
    } catch {
      // Skip a malformed/partial NDJSON line.
    }
  });
  return full;
}
