/**
 * The API-key setup wizard — the UI end of the Stage-2 onboarding handoff.
 *
 * Purely presentational: it renders when {@link useGateway} reports a
 * `trigger_key_wizard` handoff and knows nothing about HTTP or the gateway. The
 * `provider` and `status` come straight from the decoded handoff payload.
 */

"use client";

import type { WizardState } from "@joka-7/modeldispatcher-client/react";

export interface KeyWizardProps {
  /** The active handoff state, or `null` when the wizard is closed. */
  wizard: WizardState | null;
  /** Called when the user saves a key or dismisses the modal. */
  onClose: () => void;
}

export function KeyWizard({ wizard, onClose }: KeyWizardProps): JSX.Element | null {
  if (!wizard) return null;

  return (
    <div className="modal-backdrop" onClick={onClose} role="presentation">
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="key-wizard-title"
        onClick={(event) => event.stopPropagation()}
      >
        <span className="badge">
          HTTP {wizard.status} · {wizard.action}
        </span>
        <h3 id="key-wizard-title">Add your own API key</h3>
        <p>
          {wizard.detail ??
            `Free usage for ${wizard.provider} is exhausted. Add a key to continue.`}
        </p>
        <label htmlFor="api-key">{wizard.provider} API key</label>
        <input
          id="api-key"
          type="password"
          autoComplete="off"
          placeholder={`${wizard.provider} API key`}
        />
        <div className="modal-actions">
          <button type="button" className="primary" onClick={onClose}>
            Save &amp; continue
          </button>
          <button type="button" onClick={onClose}>
            Dismiss
          </button>
        </div>
      </div>
    </div>
  );
}
