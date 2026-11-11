/**
 * Google Gemini — direct browser call, no SDK. The key travels in a header
 * (`x-goog-api-key`) rather than the `?key=` query string: a URL ends up in
 * proxy/server access logs and browser history, a header does not.
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

interface GeminiPart {
  text: string;
}
interface GeminiContent {
  role: "user" | "model";
  parts: GeminiPart[];
}

function toContents(messages: readonly ChatMessage[]): GeminiContent[] {
  return messages
    .filter((m) => m.role !== "system")
    .map((m) => ({ role: m.role === "assistant" ? "model" : "user", parts: [{ text: m.content }] }));
}

function systemInstructionOf(messages: readonly ChatMessage[], explicit?: string): string | undefined {
  return explicit ?? messages.find((m) => m.role === "system")?.content;
}

function buildBody(messages: readonly ChatMessage[], options: RequestOptions) {
  const system = systemInstructionOf(messages, options.systemInstruction);
  return {
    contents: toContents(messages),
    generationConfig: {
      maxOutputTokens: options.maxTokens ?? DEFAULT_MAX_TOKENS,
      ...(options.jsonMode ? { responseMimeType: "application/json" } : {}),
    },
    ...(system ? { systemInstruction: { parts: [{ text: system }] } } : {}),
  };
}

export async function completeGemini(
  cfg: ProviderCallConfig,
  messages: readonly ChatMessage[],
  options: RequestOptions = {},
): Promise<string> {
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(cfg.model)}:generateContent`;
  const res = await fetchWithRetry(
    url,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-goog-api-key": cfg.apiKey },
      body: JSON.stringify(buildBody(messages, options)),
    },
    options.signal,
  );
  if (!res.ok) throw new Error(await describeHttpError(res));
  const data = await res.json();
  return data.candidates?.[0]?.content?.parts?.[0]?.text ?? "";
}

export async function streamGemini(
  cfg: ProviderCallConfig,
  messages: readonly ChatMessage[],
  onChunk: (fullTextSoFar: string) => void,
  options: RequestOptions = {},
): Promise<string> {
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(cfg.model)}:streamGenerateContent?alt=sse`;
  const res = await fetchWithRetry(
    url,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-goog-api-key": cfg.apiKey },
      body: JSON.stringify(buildBody(messages, options)),
    },
    options.signal,
  );
  if (!res.ok) throw new Error(await describeHttpError(res));

  let full = "";
  await consumeLines(res, (line) => {
    if (!line.startsWith("data: ")) return;
    const raw = line.slice(6).trim();
    try {
      const text = JSON.parse(raw).candidates?.[0]?.content?.parts?.[0]?.text;
      if (text) {
        full += text;
        onChunk(full);
      }
    } catch {
      // Skip a malformed/partial SSE frame — the next line may complete it.
    }
  });
  return full;
}

const SKIP_SIGNATURE = "skip_thought_signature_validator";

/** Finish reasons that still carry a usable turn. */
const GEMINI_NORMAL_FINISH = new Set(["STOP", "MAX_TOKENS", undefined]);

const GEMINI_UNSUPPORTED_SCHEMA_KEYS = new Set(["additionalProperties", "$schema"]);

/** Drop the JSON Schema keys Gemini's function declarations reject, at every depth. */
export function geminiSchema(schema: unknown): unknown {
  if (Array.isArray(schema)) return schema.map(geminiSchema);
  if (typeof schema !== "object" || schema === null) return schema;
  return Object.fromEntries(
    Object.entries(schema)
      .filter(([key]) => !GEMINI_UNSUPPORTED_SCHEMA_KEYS.has(key))
      .map(([key, value]) => [key, geminiSchema(value)]),
  );
}

function functionDeclaration(tool: ToolSpec) {
  const properties = tool.parameters["properties"];
  const hasArguments = typeof properties === "object" && properties !== null && Object.keys(properties).length > 0;
  // Gemini rejects an object schema with no properties: a no-argument tool omits it.
  return {
    name: tool.name,
    description: tool.description,
    ...(hasArguments ? { parameters: geminiSchema(tool.parameters) } : {}),
  };
}

type GeminiToolPart =
  | { text: string }
  | { functionCall: { name: string; args: Readonly<Record<string, unknown>> }; thoughtSignature?: string }
  | { functionResponse: { name: string; response: { result: string } | { error: string } } };

function toToolContents(messages: readonly ToolChatMessage[]): { role: "user" | "model"; parts: GeminiToolPart[] }[] {
  return messages
    .filter((m) => m.role !== "system")
    .map((m) => {
      if (m.role === "tool") {
        return {
          role: "user" as const,
          parts: m.results.map((r) => ({
            functionResponse: { name: r.name, response: r.isError ? { error: r.content } : { result: r.content } },
          })),
        };
      }
      if ("toolCalls" in m) {
        return {
          role: "model" as const,
          parts: [
            ...(m.content ? [{ text: m.content }] : []),
            ...m.toolCalls.map((c) => ({
              functionCall: { name: c.name, args: c.arguments },
              // Thinking models reject calls without one; calls made by another
              // provider (after a fallback) get Google's documented placeholder.
              thoughtSignature: c.signature ?? SKIP_SIGNATURE,
            })),
          ],
        };
      }
      return { role: m.role === "assistant" ? ("model" as const) : ("user" as const), parts: [{ text: m.content }] };
    });
}

interface GeminiResponsePart {
  text?: string;
  functionCall?: { id?: string; name?: string; args?: Record<string, unknown> };
  thoughtSignature?: string;
}

/** One non-streaming turn with tools available. */
export async function completeWithToolsGemini(
  cfg: ProviderCallConfig,
  messages: readonly ToolChatMessage[],
  tools: readonly ToolSpec[],
  options: RequestOptions = {},
): Promise<ToolTurn> {
  const system = options.systemInstruction ?? systemTurnOf(messages);
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(cfg.model)}:generateContent`;
  const res = await fetchWithRetry(
    url,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-goog-api-key": cfg.apiKey },
      body: JSON.stringify({
        contents: toToolContents(messages),
        generationConfig: { maxOutputTokens: options.maxTokens ?? DEFAULT_MAX_TOKENS },
        ...(system ? { systemInstruction: { parts: [{ text: system }] } } : {}),
        ...(tools.length ? { tools: [{ functionDeclarations: tools.map(functionDeclaration) }] } : {}),
      }),
    },
    options.signal,
  );
  if (!res.ok) throw new Error(await describeHttpError(res));
  const data = await res.json();
  const candidate = data.candidates?.[0];
  if (!candidate) throw new Error(`Gemini returned no answer (${data.promptFeedback?.blockReason ?? "no candidates"})`);
  if (!GEMINI_NORMAL_FINISH.has(candidate.finishReason)) throw new Error(`Gemini stopped: ${candidate.finishReason}`);
  const parts: GeminiResponsePart[] = candidate.content?.parts ?? [];
  if (parts.length === 0) throw new Error(`Gemini returned an empty turn (${candidate.finishReason ?? "no reason"})`);
  if (candidate.finishReason === "MAX_TOKENS" && parts.some((p) => p.functionCall)) {
    throw new Error("Gemini ran out of tokens in the middle of a tool call");
  }
  return {
    text: parts.map((p) => p.text ?? "").join(""),
    toolCalls: parts
      .filter((p) => p.functionCall)
      .map((p) => ({
        id: p.functionCall?.id ?? "", // often absent; the tool loop numbers it then
        name: p.functionCall?.name ?? "",
        arguments: p.functionCall?.args ?? {},
        ...(p.thoughtSignature ? { signature: p.thoughtSignature } : {}),
      })),
  };
}
