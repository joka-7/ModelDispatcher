/**
 * modeldispatcher-react-ui — public API surface.
 *
 * Three components for every app's AI settings: `ModelPicker` (a pure
 * settings screen — provider/model/key, and saving a favorite free AI app;
 * nothing in it ever navigates), `AskExternallyButton` (the action that
 * actually opens the saved favorite, meant to live wherever the user
 * composes a question, not on the settings screen), and
 * `PasteExternalReply` (captures the raw text the user pastes back from
 * that external chat — format-agnostic; parsing it is the app's own job).
 */

export { ModelPicker } from "./ModelPicker.js";
export type { ModelPickerProps } from "./ModelPicker.js";
export { AskExternallyButton } from "./AskExternallyButton.js";
export type { AskExternallyButtonProps } from "./AskExternallyButton.js";
export { PasteExternalReply } from "./PasteExternalReply.js";
export type { PasteExternalReplyProps } from "./PasteExternalReply.js";
