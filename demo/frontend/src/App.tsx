import { useCallback, useEffect, useState } from "react";
import {
  dispatch,
  fetchQuota,
  type DispatchOutcome,
  type QuotaStatus,
} from "./api";

const TENANT_ID = "demo-tenant";

export function App() {
  const [prompt, setPrompt] = useState(
    "Design and prove correct a rate limiter, step by step.",
  );
  const [simulate, setSimulate] = useState(false);
  const [busy, setBusy] = useState(false);
  const [outcome, setOutcome] = useState<DispatchOutcome | null>(null);
  const [quota, setQuota] = useState<QuotaStatus | null>(null);
  const [wizardOpen, setWizardOpen] = useState(false);

  const refreshQuota = useCallback(async () => {
    setQuota(await fetchQuota(TENANT_ID));
  }, []);

  useEffect(() => {
    void refreshQuota();
  }, [refreshQuota]);

  const onDispatch = useCallback(async () => {
    if (!prompt.trim() || busy) return;
    setBusy(true);
    try {
      const result = await dispatch(prompt, TENANT_ID, simulate);
      setOutcome(result);
      if (result.kind === "handoff") setWizardOpen(true);
      await refreshQuota();
    } finally {
      setBusy(false);
    }
  }, [prompt, simulate, busy, refreshQuota]);

  return (
    <div className="shell">
      <header className="masthead">
        <h1>
          Model<span className="accent">Dispatcher</span>
        </h1>
        <p>Resilient AI gateway — routing, fallback, quota &amp; onboarding, live.</p>
      </header>

      <main className="grid">
        <section className="panel">
          <h2>Prompt console</h2>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows={5}
            spellCheck={false}
          />
          <label className="toggle">
            <input
              type="checkbox"
              checked={simulate}
              onChange={(e) => setSimulate(e.target.checked)}
            />
            Simulate primary rate-limit (force a fallback)
          </label>
          <button className="primary" onClick={onDispatch} disabled={busy}>
            {busy ? "Dispatching…" : "Dispatch"}
          </button>
          <p className="hint">
            Tip: short prompts triage to free/cheap tiers; long reasoning prompts
            reserve premium. Keep dispatching to hit the free-tier limit and
            trigger the key wizard.
          </p>
        </section>

        <section className="panel">
          <h2>Trace</h2>
          {outcome ? <Trace outcome={outcome} /> : <Empty />}
        </section>

        <section className="panel">
          <h2>Tenant quota</h2>
          {quota ? <QuotaMeters quota={quota} /> : <Empty />}
        </section>
      </main>

      {wizardOpen && outcome?.kind === "handoff" && (
        <KeyWizard
          provider={outcome.handoff.provider}
          detail={outcome.handoff.detail}
          status={outcome.status}
          onClose={() => setWizardOpen(false)}
        />
      )}
    </div>
  );
}

function Trace({ outcome }: { outcome: DispatchOutcome }) {
  if (outcome.kind === "error") {
    return <p className="error">HTTP {outcome.status}: {outcome.detail}</p>;
  }
  if (outcome.kind === "handoff") {
    return (
      <p className="error">
        HTTP {outcome.status} · quota exceeded → key wizard triggered.
      </p>
    );
  }
  const { result } = outcome;
  return (
    <div>
      <div className="row">
        <span className={`badge tier-${result.complexity.toLowerCase()}`}>
          {result.complexity}
        </span>
        <span className="badge muted">{result.stop_reason}</span>
        <span className="badge muted">{result.usage.total} tokens</span>
      </div>
      {result.steps.map((step, i) => (
        <div key={i} className="step">
          <div className="chips">
            {step.attempts.map((a, j) => (
              <span
                key={j}
                className={`chip ${a.error ? "chip-fail" : "chip-ok"}`}
                title={a.error ?? "served"}
              >
                {a.provider}
                {a.error ? ` · ${a.error}` : " ✓"}
              </span>
            ))}
          </div>
        </div>
      ))}
      <pre className="final">{result.final}</pre>
    </div>
  );
}

function QuotaMeters({ quota }: { quota: QuotaStatus }) {
  return (
    <div className="meters">
      {quota.windows.map((w) => {
        const pct = Math.min(100, Math.round((w.used / w.limit) * 100));
        const level = pct >= 100 ? "full" : pct >= 90 ? "warn" : "ok";
        return (
          <div key={w.name} className="meter">
            <div className="meter-label">
              <span>{w.name}</span>
              <span>
                {w.used} / {w.limit}
              </span>
            </div>
            <div className="meter-track">
              <div className={`meter-fill ${level}`} style={{ width: `${pct}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function KeyWizard({
  provider,
  detail,
  status,
  onClose,
}: {
  provider: string;
  detail?: string;
  status: number;
  onClose: () => void;
}) {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <span className="badge muted">HTTP {status} · trigger_key_wizard</span>
        <h3>Add your own API key</h3>
        <p>{detail ?? `Free usage for ${provider} is exhausted.`}</p>
        <p className="hint">
          This modal is the Stage-2 onboarding handoff: the gateway returned a
          structured <code>quota_exceeded</code> payload for{" "}
          <code>{provider}</code>, and the front end launched its key wizard.
        </p>
        <input placeholder={`${provider} API key (demo — not sent)`} />
        <div className="modal-actions">
          <button className="primary" onClick={onClose}>
            Save &amp; continue
          </button>
          <button onClick={onClose}>Dismiss</button>
        </div>
      </div>
    </div>
  );
}

function Empty() {
  return <p className="hint">Nothing yet — dispatch a prompt.</p>;
}
