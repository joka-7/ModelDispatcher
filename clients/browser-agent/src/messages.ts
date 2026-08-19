/**
 * Normalise a UI's chat history into a provider-safe message list: strict
 * role validation, length capping, and merging consecutive same-role
 * messages — Anthropic and Gemini both require strict user/assistant
 * alternation starting with "user", which raw UI state doesn't guarantee.
 */

import type { ChatMessage, ChatRole } from "./types.js";

const VALID_TURN_ROLES = new Set<ChatRole>(["user", "assistant"]);
const MAX_MESSAGE_LENGTH = 4000;

export interface BuildMessagesOptions {
  /** If true, always append a trailing filler user turn (e.g. to kick off a
   * greeting flow) instead of only when the history would otherwise start
   * with "assistant". */
  forceTrailingFiller?: boolean;
  /** The filler turn's content when one is needed to satisfy user-first
   * ordering. Defaults to "begin". */
  fillerContent?: string;
  /** Marker content to drop entirely rather than treat as a real turn
   * (e.g. a UI-internal "simulate opening" sentinel). */
  dropContent?: string;
}

/**
 * Build a provider-safe chat history from UI messages: validates/coerces
 * roles, caps message length, drops sentinel content, ensures user-first
 * ordering, and merges consecutive same-role turns (required by
 * Anthropic/Gemini's strict alternation).
 */
export function buildMessages(
  uiMessages: readonly ChatMessage[],
  options: BuildMessagesOptions = {},
): ChatMessage[] {
  const { forceTrailingFiller = false, fillerContent = "begin", dropContent } = options;

  let messages = uiMessages
    .map(({ role, content }): ChatMessage => ({
      role: VALID_TURN_ROLES.has(role) ? role : "user",
      content: String(content ?? "").trim().slice(0, MAX_MESSAGE_LENGTH),
    }))
    .filter((m) => m.content.length > 0 && (dropContent === undefined || m.content !== dropContent));

  if (forceTrailingFiller) {
    messages = [...messages, { role: "user", content: fillerContent }];
  } else if (messages.length > 0 && messages[0]?.role === "assistant") {
    messages = [{ role: "user", content: fillerContent }, ...messages];
  }

  const merged: ChatMessage[] = [];
  for (const message of messages) {
    const last = merged.at(-1);
    if (last && last.role === message.role) {
      merged[merged.length - 1] = { role: last.role, content: `${last.content}\n\n${message.content}` };
    } else {
      merged.push(message);
    }
  }
  return merged.length > 0 ? merged : [{ role: "user", content: fillerContent }];
}
