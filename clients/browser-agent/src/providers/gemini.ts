/**
 * Google Gemini — direct browser call, no SDK. The key travels in a header
 * (`x-goog-api-key`) rather than the `?key=` query string: a URL ends up in
 * proxy/server access logs and browser history, a header does not.
 */

import { consumeLines, describeHttpError, fetchWithRetry } from "../http.js";
import type { AgentConfig, ChatMessage, RequestOptions } from "../types.js";

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
  cfg: AgentConfig,
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
  cfg: AgentConfig,
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
