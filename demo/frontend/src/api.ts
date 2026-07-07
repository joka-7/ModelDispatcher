// Typed client for the ModelDispatcher demo backend.

export interface Attempt {
  provider: string;
  error: string | null;
}

export interface Step {
  message: string | null;
  usage: number;
  attempts: Attempt[];
}

export interface DispatchResult {
  final: string | null;
  stop_reason: string;
  complexity: string;
  usage: { prompt: number; completion: number; total: number };
  steps: Step[];
}

export interface Handoff {
  error: string;
  provider: string;
  action: string;
  detail?: string;
}

export interface QuotaWindow {
  name: string;
  used: number;
  limit: number;
  period_seconds: number;
}

export interface QuotaStatus {
  tenant_id: string;
  windows: QuotaWindow[];
}

// A dispatch either completes with a result or is rejected with a handoff plus
// the HTTP status the gateway chose (402 billing wall / 429 rate window).
export type DispatchOutcome =
  | { kind: "ok"; result: DispatchResult }
  | { kind: "handoff"; status: number; handoff: Handoff }
  | { kind: "error"; status: number; detail: string };

export async function dispatch(
  prompt: string,
  tenantId: string,
  simulateRateLimit: boolean,
): Promise<DispatchOutcome> {
  const res = await fetch("/api/dispatch", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      prompt,
      tenant_id: tenantId,
      simulate_rate_limit: simulateRateLimit,
    }),
  });
  const body = await res.json();
  if (res.ok) {
    return { kind: "ok", result: body as DispatchResult };
  }
  if (body?.action === "trigger_key_wizard") {
    return { kind: "handoff", status: res.status, handoff: body as Handoff };
  }
  return { kind: "error", status: res.status, detail: body?.detail ?? "error" };
}

export async function fetchQuota(tenantId: string): Promise<QuotaStatus> {
  const res = await fetch(`/api/quota?tenant_id=${encodeURIComponent(tenantId)}`);
  return (await res.json()) as QuotaStatus;
}
