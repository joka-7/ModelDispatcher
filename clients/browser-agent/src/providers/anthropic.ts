/**
 * Anthropic Claude — direct browser call via raw fetch, no SDK dependency.
 * `anthropic-dangerous-direct-browser-access` is the header the official SDK
 * sends under `dangerouslyAllowBrowser` — acceptable here because the user
 * supplies their own key on their own machine; there is no backend to hide
 * it behind in the first place.
 */

import { systemTurnOf } from "../toolMessages.js";
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
const ANTHROPIC_URL = "https://api.anthropic.com/v1/messages";

function toApiMessages(messages: readonly ChatMessage[]) {
  return messages.filter((m) => m.role !== "system").map((m) => ({ role: m.role, content: m.content }));
}

function systemOf(messages: readonly ChatMessage[], explicit?: string): string | undefined {
  return explicit ?? messages.find((m) => m.role === "system")?.content;
}

function buildBody(cfg: ProviderCallConfig, messages: readonly ChatMessage[], options: RequestOptions, stream: boolean) {
  const system = systemOf(messages, options.systemInstruction);
  return {
    model: cfg.model,
    max_tokens: options.maxTokens ?? DEFAULT_MAX_TOKENS,
    ...(system ? { system } : {}),
    messages: toApiMessages(messages),
    ...(stream ? { stream: true } : {}),
  };
}

function headers(cfg: ProviderCallConfig): HeadersInit {
  return {
    "Content-Type": "application/json",
    "x-api-key": cfg.apiKey,
    "anthropic-version": "2023-06-01",
    "anthropic-dangerous-direct-browser-access": "true",
  };
}

export async function completeAnthropic(
  cfg: ProviderCallConfig,
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
  cfg: ProviderCallConfig,
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

function toToolApiMessages(messages: readonly ToolChatMessage[]) {
  return messages
    .filter((m) => m.role !== "system")
    .map((m) => {
      if (m.role === "tool") {
        return {
          role: "user",
          content: m.results.map((r) => ({
            type: "tool_result",
            tool_use_id: r.callId,
            content: r.content,
            ...(r.isError ? { is_error: true } : {}),
          })),
        };
      }
      if ("toolCalls" in m) {
        return {
          role: "assistant",
          content: [
            ...(m.content ? [{ type: "text", text: m.content }] : []),
            ...m.toolCalls.map((c) => ({ type: "tool_use", id: c.id, name: c.name, input: c.arguments })),
          ],
        };
      }
      return { role: m.role, content: m.content };
    });
}

interface AnthropicBlock {
  type?: string;
  text?: string;
  id?: string;
  name?: string;
  input?: Record<string, unknown>;
}

/** One non-streaming turn with tools available. */
export async function completeWithToolsAnthropic(
  cfg: ProviderCallConfig,
  messages: readonly ToolChatMessage[],
  tools: readonly ToolSpec[],
  options: RequestOptions = {},
): Promise<ToolTurn> {
  const system = options.systemInstruction ?? systemTurnOf(messages);
  const res = await fetchWithRetry(
    ANTHROPIC_URL,
    {
      method: "POST",
      headers: headers(cfg),
      body: JSON.stringify({
        model: cfg.model,
        max_tokens: options.maxTokens ?? DEFAULT_MAX_TOKENS,
        ...(system ? { system } : {}),
        messages: toToolApiMessages(messages),
        ...(tools.length
          ? { tools: tools.map((t) => ({ name: t.name, description: t.description, input_schema: t.parameters })) }
          : {}),
      }),
    },
    options.signal,
  );
  if (!res.ok) throw new Error(await describeHttpError(res));
  const data = await res.json();
  const blocks: AnthropicBlock[] = data.content ?? [];
  if (data.stop_reason === "refusal") throw new Error("Anthropic declined to answer");
  if (data.stop_reason === "max_tokens" && blocks.some((b) => b.type === "tool_use")) {
    // The tool input may be cut off: running it would act on partial arguments.
    throw new Error("Anthropic ran out of tokens in the middle of a tool call");
  }
  if (blocks.length === 0) throw new Error(`Anthropic returned an empty turn (${data.stop_reason ?? "no reason"})`);
  return {
    text: blocks
      .filter((b) => b.type === "text")
      .map((b) => b.text ?? "")
      .join(""),
    toolCalls: blocks
      .filter((b) => b.type === "tool_use")
      .map((b) => ({ id: b.id ?? "", name: b.name ?? "", arguments: b.input ?? {} })),
  };
}
