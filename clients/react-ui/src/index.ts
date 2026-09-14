/**
 * @joka-7/modeldispatcher-react-ui — public API surface.
 *
 * Two components for every app's AI settings: `ModelPicker` (a pure
 * settings screen — provider/model/key, and saving a favorite free AI app;
 * nothing in it ever navigates) and `AskExternallyButton` (the action that
 * actually opens the saved favorite, meant to live wherever the user
 * composes a question, not on the settings screen).
 */

export { ModelPicker } from "./ModelPicker.js";
export type { ModelPickerProps } from "./ModelPicker.js";
export { AskExternallyButton } from "./AskExternallyButton.js";
export type { AskExternallyButtonProps } from "./AskExternallyButton.js";
