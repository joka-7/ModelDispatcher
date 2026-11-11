/** Shared fixtures for the providers' tool-turn tests. */

import { vi } from "vitest";

import type { ToolChatMessage, ToolSpec } from "../../src/types.js";

export function mockReply(body: unknown): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(body)));
  globalThis.fetch = fetchMock as unknown as typeof fetch;
  return fetchMock;
}

export function sentBody(fetchMock: ReturnType<typeof vi.fn>): Record<string, unknown> {
  const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
  return JSON.parse(init.body as string);
}

export const quote: ToolSpec = {
  name: "get_quote",
  description: "Latest price",
  parameters: {
    type: "object",
    properties: { symbol: { type: "string" } },
    required: ["symbol"],
    additionalProperties: false,
  },
};
export const portfolio: ToolSpec = { name: "get_portfolio", description: "The user's holdings", parameters: { type: "object", properties: {} } };

/** A conversation one tool round in: asked, called (one ok, one failed), answered. */
export const history: ToolChatMessage[] = [
  { role: "system", content: "Be brief." },
  { role: "user", content: "AAPL price?" },
  {
    role: "assistant",
    content: "Checking.",
    toolCalls: [
      { id: "c1", name: "get_quote", arguments: { symbol: "AAPL" }, signature: "sig-1" },
      { id: "c2", name: "get_portfolio", arguments: {} },
    ],
  },
  {
    role: "tool",
    results: [
      { callId: "c1", name: "get_quote", content: "190.5", isError: false },
      { callId: "c2", name: "get_portfolio", content: "tool error: locked", isError: true },
    ],
  },
];
