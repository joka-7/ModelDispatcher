/**
 * Ollama — a local (or self-hosted) model server, no API key. Always uses
 * `/api/chat` (message-list based) rather than switching between `/generate`
 * and `/chat` per call shape — a single-turn prompt is just a one-message
 * chat, so one code path covers both without the caller needing to know
 * which Ollama endpoint that implies.
 */

import { consumeLines, fetchWithRetry, validateOllamaUrl } from "../http.js";
import type {
  ChatMessage,
  ProviderCallConfig,
  RequestOptions,
  ToolChatMessage,
  ToolSpec,
  ToolTurn,
} from "../types.js";

const DEFAULT_MAX_TOKENS = 1024;

function toApiMessages(messages: readonly ChatMessage[], systemInstruction?: string) {
  const hasSystemTurn = messages.some((m) => m.role === "system");
  const system = !hasSystemTurn && systemInstruction ? [{ role: "system", content: systemInstruction }] : [];
  return [...system, ...messages.map((m) => ({ role: m.role, content: m.content }))];
}

function buildBody(cfg: ProviderCallConfig, messages: readonly ChatMessage[], options: RequestOptions, stream: boolean) {
  return {
    model: cfg.model,
    messages: toApiMessages(messages, options.systemInstruction),
    stream,
    options: { num_predict: options.maxTokens ?? DEFAULT_MAX_TOKENS },
  };
}

export async function completeOllama(
  cfg: ProviderCallConfig,
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
  cfg: ProviderCallConfig,
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

function toToolApiMessages(messages: readonly ToolChatMessage[], systemInstruction?: string) {
  const hasSystemTurn = messages.some((m) => m.role === "system");
  const system = !hasSystemTurn && systemInstruction ? [{ role: "system", content: systemInstruction }] : [];
  return [
    ...system,
    ...messages.flatMap((m): Record<string, unknown>[] => {
      if (m.role === "tool") return m.results.map((r) => ({ role: "tool", tool_name: r.name, content: r.content }));
      if ("toolCalls" in m) {
        return [
          {
            role: "assistant",
            content: m.content,
            tool_calls: m.toolCalls.map((c) => ({ function: { name: c.name, arguments: c.arguments } })),
          },
        ];
      }
      return [{ role: m.role, content: m.content }];
    }),
  ];
}

interface OllamaToolCall {
  function?: { name?: string; arguments?: Record<string, unknown> };
}

/** One non-streaming turn with tools available; needs a tool-capable local model. */
export async function completeWithToolsOllama(
  cfg: ProviderCallConfig,
  messages: readonly ToolChatMessage[],
  tools: readonly ToolSpec[],
  options: RequestOptions = {},
): Promise<ToolTurn> {
  const baseUrl = validateOllamaUrl(cfg.ollamaUrl);
  const res = await fetchWithRetry(
    `${baseUrl}/api/chat`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: cfg.model,
        messages: toToolApiMessages(messages, options.systemInstruction),
        stream: false,
        options: { num_predict: options.maxTokens ?? DEFAULT_MAX_TOKENS },
        ...(tools.length
          ? {
              tools: tools.map((t) => ({
                type: "function",
                function: { name: t.name, description: t.description, parameters: t.parameters },
              })),
            }
          : {}),
      }),
    },
    options.signal,
  );
  if (!res.ok) throw new Error(`Ollama error: HTTP ${res.status}. Is Ollama running?`);
  const data = await res.json();
  const calls: OllamaToolCall[] = data.message?.tool_calls ?? [];
  return {
    text: data.message?.content ?? "",
    toolCalls: calls.map((c) => ({ id: "", name: c.function?.name ?? "", arguments: c.function?.arguments ?? {} })),
  };
}
