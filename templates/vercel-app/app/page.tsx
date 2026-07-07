/**
 * Reference page: dispatch a prompt through the gateway and react to outcomes.
 *
 * Shows the whole client contract in one place — `useGateway` gives a typed
 * `dispatch` plus reactive `wizard` state; the component switches on
 * {@link DispatchOutcome.kind} for inline feedback while the shared bus drives
 * the {@link KeyWizard} independently. Nothing here knows about HTTP status codes.
 */

"use client";

import { useCallback, useState } from "react";
import type { DispatchOutcome } from "@modeldispatcher/client";
import { useGateway } from "@modeldispatcher/client/react";

import { gateway } from "./lib/gateway";
import { KeyWizard } from "./components/KeyWizard";

export default function Page(): JSX.Element {
  const { dispatch, wizard, dismissWizard } = useGateway(gateway);
  const [prompt, setPrompt] = useState("Summarise the CAP theorem in three lines.");
  const [busy, setBusy] = useState(false);
  const [outcome, setOutcome] = useState<DispatchOutcome | null>(null);

  const onDispatch = useCallback(async () => {
    if (!prompt.trim() || busy) return;
    setBusy(true);
    try {
      setOutcome(await dispatch({ prompt, tenant_id: "demo-tenant" }));
    } finally {
      setBusy(false);
    }
  }, [prompt, busy, dispatch]);

  return (
    <main className="shell">
      <h1>ModelDispatcher — Vercel template</h1>

      <textarea
        value={prompt}
        rows={4}
        spellCheck={false}
        onChange={(event) => setPrompt(event.target.value)}
      />
      <button type="button" className="primary" onClick={onDispatch} disabled={busy}>
        {busy ? "Dispatching…" : "Dispatch"}
      </button>

      {outcome && <OutcomeView outcome={outcome} />}
      <KeyWizard wizard={wizard} onClose={dismissWizard} />
    </main>
  );
}

function OutcomeView({ outcome }: { outcome: DispatchOutcome }): JSX.Element {
  switch (outcome.kind) {
    case "ok":
      return <pre className="final">{outcome.result.final}</pre>;
    case "handoff":
      return (
        <p className="notice">
          Quota exceeded (HTTP {outcome.status}) → key wizard opened.
        </p>
      );
    case "error":
      return (
        <p className="error">
          HTTP {outcome.status}: {outcome.error.error}
          {outcome.error.detail ? ` — ${outcome.error.detail}` : ""}
        </p>
      );
    case "network":
      return <p className="error">Network {outcome.error.kind}: {outcome.error.message}</p>;
  }
}
