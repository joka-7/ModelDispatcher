/**
 * React binding for {@link GatewayClient}.
 *
 * Subscribes to the client's event bus and lifts any `trigger_key_wizard`
 * handoff into local state, so a component can render the API-key wizard
 * declaratively without threading the dispatch outcome down through props. The
 * `dispatch` it returns still yields the typed {@link DispatchOutcome} for
 * call-site handling — both paths, one decode.
 */

import { useCallback, useEffect, useState } from "react";

import type { GatewayClient, DispatchOptions } from "../client.js";
import type { DispatchOutcome, GatewayResult, HandoffAction } from "../types.js";

/** UI-facing snapshot of an active key-wizard handoff. */
export interface WizardState {
  readonly provider: string;
  readonly status: number;
  readonly action: HandoffAction;
  readonly detail?: string;
}

/** Return value of {@link useGateway}. */
export interface UseGatewayResult<T> {
  /** Dispatch a request; resolves to a typed outcome (never rejects). */
  dispatch: (body: unknown, options?: DispatchOptions) => Promise<DispatchOutcome<T>>;
  /** Non-null when the gateway asked the UI to open the key wizard. */
  wizard: WizardState | null;
  /** Dismiss the wizard (e.g. after the user saves a key). */
  dismissWizard: () => void;
}

/**
 * Bind a {@link GatewayClient} to React state.
 *
 * @param client - A stable client instance (create it once, e.g. in a module or
 *   a context provider, not inside render).
 */
export function useGateway<T = GatewayResult>(
  client: GatewayClient,
): UseGatewayResult<T> {
  const [wizard, setWizard] = useState<WizardState | null>(null);

  useEffect(() => {
    const unsubscribe = client.bus.on("handoff", ({ status, handoff }) => {
      if (handoff.action === "trigger_key_wizard") {
        setWizard({
          provider: handoff.provider,
          status,
          action: handoff.action,
          ...(handoff.detail !== undefined ? { detail: handoff.detail } : {}),
        });
      }
    });
    return unsubscribe;
  }, [client]);

  const dispatch = useCallback(
    (body: unknown, options?: DispatchOptions) => client.dispatch<T>(body, options),
    [client],
  );

  const dismissWizard = useCallback(() => setWizard(null), []);

  return { dispatch, wizard, dismissWizard };
}
