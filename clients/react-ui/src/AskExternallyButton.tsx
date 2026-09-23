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
}

export function AskExternallyButton({
  favorite,
  question,
  onExternalChat,
  externalChatDeps,
}: AskExternallyButtonProps): JSX.Element | null {
  const [lastResult, setLastResult] = useState<OpenExternalChatResult | null>(null);

  if (favorite === null) return null;
  const activeFavorite = favorite;
  const info = EXTERNAL_CHAT_PROVIDERS[activeFavorite];

  async function handleClick(): Promise<void> {
    const result = await openExternalChat(activeFavorite, question ?? "", externalChatDeps);
    setLastResult(result);
    onExternalChat?.(result);
  }

  return (
    <div className="md-ask-externally">
      <button type="button" className="md-ask-externally-btn" onClick={() => void handleClick()}>
        Ask {info.name}
      </button>
      {lastResult && (
        <p className="md-status" role="status">
          Opened {info.name}
          {lastResult.prefilled ? " with your question filled in" : ""}
          {lastResult.copiedToClipboard ? " — also copied to your clipboard." : "."}
        </p>
      )}
    </div>
  );
}
