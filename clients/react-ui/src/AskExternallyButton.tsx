/**
 * The action half of the no-key escape hatch.
 *
 * `ModelPicker` only lets a user pick and save a favorite free AI app — it
 * never navigates. This is the button that actually does: render it wherever
 * the user is composing a question (next to the prompt box, not on a
 * settings screen), so clicking it is an expected "do something now" action
 * rather than a surprise redirect from a preferences page.
 *
 * Renders nothing when no favorite is saved yet — there's nothing to ask.
 */

import { useState } from "react";
import {
  EXTERNAL_CHAT_PROVIDERS,
  openExternalChat,
  type ExternalChatProviderId,
  type OpenExternalChatDeps,
  type OpenExternalChatResult,
} from "modeldispatcher-browser-agent";
import { dirFor, resolveStrings, type Locale } from "./i18n.js";

export interface AskExternallyButtonProps {
  /** The saved favorite (see `ModelPicker`'s `externalChatFavorite` /
   * `loadExternalChatFavorite` in `modeldispatcher-browser-agent`).
   * Renders nothing when `null`. */
  favorite: ExternalChatProviderId | null;
  /** The user's current question/prompt, carried into the opened product.
   * Omit to open an empty compose box. */
  question?: string;
  /** Called after `openExternalChat` opens a tab, e.g. to show a toast. */
  onExternalChat?: (result: OpenExternalChatResult) => void;
  /** Injected `openExternalChat` deps — for tests or a non-browser host. */
  externalChatDeps?: OpenExternalChatDeps;
  /** UI language for this button's own label/status text. Defaults to English. */
  locale?: Locale;
}

export function AskExternallyButton({
  favorite,
  question,
  onExternalChat,
  externalChatDeps,
  locale = "en",
}: AskExternallyButtonProps): JSX.Element | null {
  const [lastResult, setLastResult] = useState<OpenExternalChatResult | null>(null);

  if (favorite === null) return null;
  const activeFavorite = favorite;
  const info = EXTERNAL_CHAT_PROVIDERS[activeFavorite];
  const s = resolveStrings(locale).askExternally;

  async function handleClick(): Promise<void> {
    const result = await openExternalChat(activeFavorite, question ?? "", externalChatDeps);
    setLastResult(result);
    onExternalChat?.(result);
  }

  return (
    <div className="md-ask-externally" dir={dirFor(locale)}>
      <button type="button" className="md-ask-externally-btn" onClick={() => void handleClick()}>
        {s.askButton(info.name)}
      </button>
      {lastResult && (
        <p className="md-status" role="status">
          {s.openedPrefix(info.name)}
          {lastResult.prefilled ? s.openedWithQuestion : ""}
          {lastResult.copiedToClipboard ? s.copiedToClipboard : "."}
        </p>
      )}
    </div>
  );
}
