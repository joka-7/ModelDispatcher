/**
 * The missing link for the no-key escape hatch: once `AskExternallyButton`
 * opens a favorite in a new tab, there's no API call at all, so nothing
 * can be parsed automatically — the only way an answer gets back into the
 * app is for the user to paste it here.
 *
 * Deliberately format-agnostic: this component has no idea what shape the
 * app expects back (JSON, a specific text layout, whatever) and does no
 * parsing or validation itself. It only captures the pasted text and hands
 * it to `onApply` raw — the same "coach the format into the pre-filled
 * question, then parse whatever comes back" split every app already needs
 * to do on its own for `openExternalChat`'s `question` string.
 */

import { useState } from "react";

export interface PasteExternalReplyProps {
  /** Label shown above the textarea. */
  label?: string;
  /** Placeholder text shown in the empty textarea. */
  placeholder?: string;
  /** Apply button label. */
  applyLabel?: string;
  /** Called with the raw pasted text (trimmed) when the user clicks apply.
   * Parsing/validating it against whatever format the app asked for is
   * entirely the caller's job. The textarea clears after a successful call. */
  onApply: (rawText: string) => void;
}

export function PasteExternalReply({
  label = "Paste the AI's reply below, then apply it.",
  placeholder = "Paste the response here…",
  applyLabel = "Apply",
  onApply,
}: PasteExternalReplyProps): JSX.Element {
  const [text, setText] = useState("");
  const trimmed = text.trim();

  function handleApply(): void {
    if (!trimmed) return;
    onApply(trimmed);
    setText("");
  }

  return (
    <div className="md-paste-reply">
      <label htmlFor="md-paste-reply-input" className="md-paste-reply-label">
        {label}
      </label>
      <textarea
        id="md-paste-reply-input"
        className="md-paste-reply-textarea"
        value={text}
        onChange={(event) => setText(event.target.value)}
        placeholder={placeholder}
        rows={6}
      />
      <button type="button" className="md-paste-reply-btn" onClick={handleApply} disabled={trimmed.length === 0}>
        {applyLabel}
      </button>
    </div>
  );
}
