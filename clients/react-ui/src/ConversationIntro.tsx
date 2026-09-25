/**
 * A one-line, on-screen notice that the user is talking to AI, not a human —
 * shown before the first reply in a chat window. HighFive, JobFlowTracker,
 * and KanDOne each set a *backend* system prompt (a hidden instruction
 * telling the model its persona), but none of them told the person on the
 * other side of the screen anything: this is that visible counterpart,
 * rendered once at the top of the conversation.
 */

import { dirFor, resolveStrings, type Locale } from "./i18n.js";

export interface ConversationIntroProps {
  /** UI language for this notice's text. Defaults to English. */
  locale?: Locale;
}

export function ConversationIntro({ locale = "en" }: ConversationIntroProps): JSX.Element {
  const s = resolveStrings(locale).conversationIntro;

  return (
    <p className="md-conversation-intro" dir={dirFor(locale)} role="note">
      {s.text}
    </p>
  );
}
