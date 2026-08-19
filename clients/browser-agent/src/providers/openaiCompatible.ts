/**
 * OpenAI and Groq — both speak the same chat-completions REST shape, direct
 * from the browser, no SDK. Groq is just the same code pointed at its own
 * base URL (matches how the Python core's GroqProvider relates to
 * OpenAIProvider — same idea, browser side).
 */

import { consumeLines, describeHttpError, fetchWithRetry } from "../http.js";
import type { AgentConfig, ChatMessage, RequestOptions } from "../types.js";

const DEFAULT_MAX_TOKENS = 1024;

const BASE_URLS: Record<"openai" | "groq", string> = {
  openai: "https://api.openai.com/v1/chat/completions",
  groq: "https://api.groq.com/openai/v1/chat/completions",
};

function toApiMessages(messages: readonly ChatMessage[], systemInstruction?: string) {
  const hasSystemTurn = messages.some((m) => m.role === "system");
  const system = !hasSystemTurn && systemInstruction ? [{ role: "system", content: systemInstruction }] : [];
  return [...system, ...messages.map((m) => ({ role: m.role, content: m.content }))];
}

function buildBody(cfg: AgentConfig, messages: readonly ChatMessage[], options: RequestOptions, stream: boolean) {
  return {
    model: cfg.model,
    max_tokens: options.maxTokens ?? DEFAULT_MAX_TOKENS,
    messages: toApiMessages(messages, options.systemInstruction),
    ...(options.jsonMode ? { response_format: { type: "json_object" } } : {}),
    ...(stream ? { stream: true } : {}),
  };
}

async function request(
  provider: "openai" | "groq",
  cfg: AgentConfig,
  messages: readonly ChatMessage[],
  options: RequestOptions,
  stream: boolean,
): Promise<Response> {
  const res = await fetchWithRetry(
    BASE_URLS[provider],
    {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${cfg.apiKey}` },
      body: JSON.stringify(buildBody(cfg, messages, options, stream)),
    },
    options.signal,
  );
  if (!res.ok) throw new Error(await describeHttpError(res));
  return res;
}

export async function completeOpenAICompatible(
  provider: "openai" | "groq",
  cfg: AgentConfig,
  messages: readonly ChatMessage[],
  options: RequestOptions = {},
): Promise<string> {
  const res = await request(provider, cfg, messages, options, false);
  const data = await res.json();
  return data.choices?.[0]?.message?.content ?? "";
}

export async function streamOpenAICompatible(
  provider: "openai" | "groq",
  cfg: AgentConfig,
  messages: readonly ChatMessage[],
  onChunk: (fullTextSoFar: string) => void,
  options: RequestOptions = {},
): Promise<string> {
  const res = await request(provider, cfg, messages, options, true);
  let full = "";
  await consumeLines(res, (line) => {
    if (!line.startsWith("data: ")) return;
    const raw = line.slice(6).trim();
    if (raw === "[DONE]") return;
    try {
      const delta = JSON.parse(raw).choices?.[0]?.delta?.content;
      if (delta) {
        full += delta;
        onChunk(full);
      }
    } catch {
      // Skip a malformed/partial SSE frame.
    }
  });
  return full;
}
