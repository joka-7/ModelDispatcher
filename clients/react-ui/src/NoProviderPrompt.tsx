/**
 * The empty state a chat screen shows when no provider/key is configured yet
 * (`!isConfigReady()` in `browser-agent` terms).
 *
 * Every app that adopted `ModelPicker` had the same gap: the framework's
 * no-key escape hatch (`AskExternallyButton`, opening a free chat product
 * with no API key) only ever appeared buried in the Settings screen as a
 * "save a favorite" preference — the chat window itself just told the user
 * to go set an API key, with no way to actually talk to AI without one. This
 * renders both real options together, right where the user is about to ask
 * something: open Settings to configure a provider, or (when a favorite is
 * already saved) ask it for free right now.
 */

import {
  type ExternalChatProviderId,
  type OpenExternalChatDeps,
  type OpenExternalChatResult,
} from "modeldispatcher-browser-agent";
import { AskExternallyButton } from "./AskExternallyButton.js";
import { dirFor, resolveStrings, type Locale } from "./i18n.js";

export interface NoProviderPromptProps {
  /** The saved "ask externally" favorite, or `null` if none is picked yet. */
  favorite: ExternalChatProviderId | null;
  /** The user's current question/prompt, carried into the opened product if
   * they use the "ask externally" path. */
  question?: string;
  /** Called when the user clicks through to configure a real provider. */
  onOpenSettings: () => void;
  /** Called after `openExternalChat` opens a tab, e.g. to show a toast. */
  onExternalChat?: (result: OpenExternalChatResult) => void;
  /** Injected `openExternalChat` deps — for tests or a non-browser host. */
  externalChatDeps?: OpenExternalChatDeps;
  /** UI language. Defaults to English. */
  locale?: Locale;
}

export function NoProviderPrompt({
  favorite,
  question,
  onOpenSettings,
  onExternalChat,
  externalChatDeps,
  locale = "en",
}: NoProviderPromptProps): JSX.Element {
  const s = resolveStrings(locale).noProvider;

  return (
    <div className="md-no-provider" dir={dirFor(locale)}>
      <p className="md-no-provider-lead">{s.lead}</p>
      <div className="md-no-provider-actions">
        <button type="button" className="md-no-provider-settings-btn" onClick={onOpenSettings}>
          {s.openSettings}
        </button>
        {favorite !== null && (
          <>
            <span className="md-no-provider-divider">{s.orDivider}</span>
            <AskExternallyButton
              favorite={favorite}
              {...(question !== undefined ? { question } : {})}
              {...(onExternalChat !== undefined ? { onExternalChat } : {})}
              {...(externalChatDeps !== undefined ? { externalChatDeps } : {})}
              locale={locale}
            />
          </>
        )}
      </div>
      {favorite === null && <p className="md-no-provider-hint">{s.noFavoriteHint}</p>}
    </div>
  );
}
