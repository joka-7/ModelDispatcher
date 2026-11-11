/**
 * OpenAI and Groq — both speak the same chat-completions REST shape, direct
 * from the browser, no SDK. Groq is just the same code pointed at its own
 * base URL (matches how the Python core's GroqProvider relates to
 * OpenAIProvider — same idea, browser side).
 */

import { consumeLines, describeHttpError, fetchWithRetry } from "../http.js";
import type {
  ChatMessage,
  ProviderCallConfig,
  RequestOptions,
  ToolChatMessage,
  ToolSpec,
  ToolTurn,
} from "../types.js";

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

function buildBody(cfg: ProviderCallConfig, messages: readonly ChatMessage[], options: RequestOptions, stream: boolean) {
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
  cfg: ProviderCallConfig,
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
  cfg: ProviderCallConfig,
  messages: readonly ChatMessage[],
  options: RequestOptions = {},
): Promise<string> {
  const res = await request(provider, cfg, messages, options, false);
  const data = await res.json();
  return data.choices?.[0]?.message?.content ?? "";
}

export async function streamOpenAICompatible(
  provider: "openai" | "groq",
  cfg: ProviderCallConfig,
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

function toToolApiMessages(messages: readonly ToolChatMessage[], systemInstruction?: string) {
  const hasSystemTurn = messages.some((m) => m.role === "system");
  const system = !hasSystemTurn && systemInstruction ? [{ role: "system", content: systemInstruction }] : [];
  return [
    ...system,
    ...messages.flatMap((m): Record<string, unknown>[] => {
      if (m.role === "tool") {
        return m.results.map((r) => ({ role: "tool", tool_call_id: r.callId, content: r.content }));
      }
      if ("toolCalls" in m) {
        return [
          {
            role: "assistant",
            content: m.content || null,
            tool_calls: m.toolCalls.map((c) => ({
              id: c.id,
              type: "function",
              function: { name: c.name, arguments: JSON.stringify(c.arguments) },
            })),
          },
        ];
      }
      return [{ role: m.role, content: m.content }];
    }),
  ];
}

interface OpenAIToolCall {
  id?: string;
  function?: { name?: string; arguments?: string };
}

/** Parse the model's tool-call arguments: a JSON string that may be empty. */
export function parseArguments(raw: string | undefined, toolName: string): Record<string, unknown> {
  if (!raw || !raw.trim()) return {};
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new Error(`Tool call ${toolName} sent arguments that are not valid JSON`);
  }
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    throw new Error(`Tool call ${toolName} sent arguments that are not a JSON object`);
  }
  return parsed as Record<string, unknown>;
}

/** One non-streaming turn with tools available (OpenAI or Groq). */
export async function completeWithToolsOpenAICompatible(
  provider: "openai" | "groq",
  cfg: ProviderCallConfig,
  messages: readonly ToolChatMessage[],
  tools: readonly ToolSpec[],
  options: RequestOptions = {},
): Promise<ToolTurn> {
  const res = await fetchWithRetry(
    BASE_URLS[provider],
    {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${cfg.apiKey}` },
      body: JSON.stringify({
        model: cfg.model,
        max_tokens: options.maxTokens ?? DEFAULT_MAX_TOKENS,
        messages: toToolApiMessages(messages, options.systemInstruction),
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
  if (!res.ok) throw new Error(await describeHttpError(res));
  const data = await res.json();
  const choice = data.choices?.[0];
  if (!choice?.message) throw new Error(`${provider} returned no answer`);
  if (choice.finish_reason === "content_filter") throw new Error(`${provider} filtered the answer`);
  const message = choice.message;
  const calls: OpenAIToolCall[] = message.tool_calls ?? [];
  if (choice.finish_reason === "length" && calls.length) {
    throw new Error(`${provider} ran out of tokens in the middle of a tool call`);
  }
  return {
    text: message.content ?? "",
    toolCalls: calls.map((c) => {
      const name = c.function?.name ?? "";
      return { id: c.id ?? "", name, arguments: parseArguments(c.function?.arguments, name) };
    }),
  };
}
