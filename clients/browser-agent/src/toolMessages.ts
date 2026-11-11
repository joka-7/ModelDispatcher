/** Helpers for the neutral tool-conversation history ({@link ToolChatMessage}). */

import type { ToolChatMessage } from "./types.js";

/** The content of the history's system turn, if it has one. */
export function systemTurnOf(messages: readonly ToolChatMessage[]): string | undefined {
  for (const m of messages) {
    if (m.role === "system") return m.content;
  }
  return undefined;
}
