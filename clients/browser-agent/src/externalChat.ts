/**
 * "Free agent" escape hatch: hand a question off to a free, public AI chat
 * web product instead of calling any API. For a BYOK app, this is what a
 * user with no API key configured (or who just doesn't want to set one up)
 * falls back to — open one of the well-known consumer chat products in a new
 * tab, with the question pre-filled where the product supports it.
 *
 * The query-prefill URL parameters below are undocumented, reverse-engineered
 * conventions (the kind of thing browser address-bar integrations and
 * "Ask X" share links rely on) — not a stable public API any vendor promises
 * to keep working, and they can change or disappear without notice. Treat
 * them as best-effort: `openExternalChat` always copies the question to the
 * clipboard too, regardless of whether a prefill parameter exists, so a
 * broken/removed parameter still leaves the user able to paste it in by hand
 * instead of silently losing their question.
 */

import type { ExternalChatProviderId, ExternalChatProviderInfo } from "./types.js";

export const EXTERNAL_CHAT_PROVIDERS: Record<ExternalChatProviderId, ExternalChatProviderInfo> = {
  chatgpt: {
    id: "chatgpt",
    name: "ChatGPT",
    homeUrl: "https://chatgpt.com/",
    buildUrl: (question) => `https://chatgpt.com/?${new URLSearchParams({ q: question, hints: "search" })}`,
  },
  claude: {
    id: "claude",
    name: "Claude",
    homeUrl: "https://claude.ai/new",
    buildUrl: (question) => `https://claude.ai/new?${new URLSearchParams({ q: question })}`,
  },
  gemini: {
    id: "gemini",
    name: "Gemini (Google AI Mode)",
    homeUrl: "https://www.google.com/",
    // gemini.google.com itself has no known prefill parameter. Google
    // Search's AI Mode does (`udm=50`), and is the more reliable target for
    // "ask Google's AI this" — that's what this actually opens.
    buildUrl: (question) => `https://www.google.com/search?${new URLSearchParams({ q: question, udm: "50" })}`,
  },
  groq: {
    id: "groq",
    name: "Groq",
    homeUrl: "https://groq.com/",
    // No known query-prefill parameter for Groq's consumer chat product —
    // opens the plain homepage; the question still goes to the clipboard.
    buildUrl: null,
  },
};

/** Minimal shape of the two browser APIs this needs — injectable so this is
 * testable outside a real browser and swappable for a non-browser host. */
export interface OpenExternalChatDeps {
  open?: (url: string) => unknown;
  clipboard?: { writeText(text: string): Promise<void> };
}

export interface OpenExternalChatResult {
  readonly provider: ExternalChatProviderId;
  readonly url: string;
  /** True if this provider has a known prefill parameter and the question
   * was actually embedded in `url`. False means `url` is just `homeUrl`. */
  readonly prefilled: boolean;
  /** True if the question was successfully copied to the clipboard — the
   * fallback path a user needs whenever `prefilled` is false, and a useful
   * safety net even when it's true. */
  readonly copiedToClipboard: boolean;
}

function defaultOpen(url: string): void {
  if (typeof window === "undefined") return;
  window.open(url, "_blank", "noopener,noreferrer");
}

function resolveClipboard(
  clipboard?: OpenExternalChatDeps["clipboard"],
): OpenExternalChatDeps["clipboard"] | undefined {
  if (clipboard) return clipboard;
  if (typeof navigator !== "undefined" && navigator.clipboard) return navigator.clipboard;
  return undefined;
}

/**
 * Open `provider`'s chat with `question`, pre-filled where a prefill
 * parameter is known, and always copy `question` to the clipboard as well.
 *
 * Never throws: a clipboard failure (permissions, a non-secure context, a
 * non-browser host) is reported via `copiedToClipboard: false` rather than
 * rejecting, since the tab still opens either way.
 */
export async function openExternalChat(
  provider: ExternalChatProviderId,
  question: string,
  deps: OpenExternalChatDeps = {},
): Promise<OpenExternalChatResult> {
  const info = EXTERNAL_CHAT_PROVIDERS[provider];
  const prefilled = info.buildUrl !== null;
  const url = info.buildUrl ? info.buildUrl(question) : info.homeUrl;

  const clipboard = resolveClipboard(deps.clipboard);
  let copiedToClipboard = false;
  if (clipboard) {
    try {
      await clipboard.writeText(question);
      copiedToClipboard = true;
    } catch {
      copiedToClipboard = false;
    }
  }

  (deps.open ?? defaultOpen)(url);

  return { provider, url, prefilled, copiedToClipboard };
}
