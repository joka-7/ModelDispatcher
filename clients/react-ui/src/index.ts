/**
 * modeldispatcher-react-ui — public API surface.
 *
 * Four components for every app's AI settings and chat UI: `ModelPicker` (a
 * pure settings screen — provider/model/key, and saving a favorite free AI
 * app; nothing in it ever navigates), `AskExternallyButton` (the action that
 * actually opens the saved favorite, meant to live wherever the user
 * composes a question, not on the settings screen), `NoProviderPrompt` (the
 * chat window's empty state when no provider is configured yet — offers
 * both "open Settings" and, when a favorite is saved, "ask it for free"
 * together, so the no-key path is reachable from the chat screen itself,
 * not only from Settings), and `PasteExternalReply` (captures the raw text
 * the user pastes back from that external chat — format-agnostic; parsing
 * it is the app's own job). `ModelPicker` and `AskExternallyButton` (and by
 * extension `NoProviderPrompt`) take an optional `locale` ("en" | "fr" |
 * "he") for their own labels/buttons/hints — see `i18n.ts`.
 */

export { ModelPicker } from "./ModelPicker.js";
export type { ModelPickerProps } from "./ModelPicker.js";
export { AskExternallyButton } from "./AskExternallyButton.js";
export type { AskExternallyButtonProps } from "./AskExternallyButton.js";
export { NoProviderPrompt } from "./NoProviderPrompt.js";
export type { NoProviderPromptProps } from "./NoProviderPrompt.js";
export { ConversationIntro } from "./ConversationIntro.js";
export type { ConversationIntroProps } from "./ConversationIntro.js";
export { PasteExternalReply } from "./PasteExternalReply.js";
export type { PasteExternalReplyProps } from "./PasteExternalReply.js";
export { STRINGS, RTL_LOCALES, resolveStrings, dirFor } from "./i18n.js";
export type {
  Locale,
  Strings,
  ModelPickerStrings,
  AskExternallyStrings,
  NoProviderStrings,
  ConversationIntroStrings,
} from "./i18n.js";
