/**
 * Public type surface for the ModelDispatcher client.
 *
 * These interfaces are the strict, versioned contract between a Vercel frontend
 * and the packaged Python gateway. The response-side types intentionally mirror
 * the gateway's `to_payload()` output (see `src/model_dispatcher/exceptions.py`
 * and `onboarding/handoff.py`): the discriminated {@link DispatchOutcome} is the
 * TypeScript view of "either a run result, a structured onboarding handoff, a
 * mapped HTTP error, or a transport failure".
 */

/** A handoff action the gateway can instruct the UI to take. */
export type HandoffAction = "trigger_key_wizard" | "upgrade_plan" | "retry_later";

/**
 * The structured Stage-2 onboarding instruction returned by the gateway.
 *
 * Serialised form (from the Python `HandoffResponse.to_payload`):
 * `{"error": "quota_exceeded", "provider": "openai", "action": "trigger_key_wizard"}`.
 */
export interface Handoff {
  /** Machine-readable error code, e.g. `"quota_exceeded"`. */
  readonly error: string;
  /** Provider whose limit was hit, so the wizard can pre-select it. */
  readonly provider: string;
  /** What the client UI should do next. */
  readonly action: HandoffAction;
  /** Optional human-readable explanation for display/logging. */
  readonly detail?: string;
}

/** A non-handoff error body mapped from a `ModelDispatcherError`. */
export interface GatewayError {
  /** Stable machine-readable slug, e.g. `"perimeter_violation"`. */
  readonly error: string;
  /** Human-readable description, when the backend supplies one. */
  readonly detail?: string;
}

/** Kinds of transport failure that never reached a well-formed HTTP response. */
export type NetworkErrorKind = "timeout" | "offline" | "retries_exhausted" | "unknown";

/** A failure to obtain any HTTP response (before status interpretation). */
export interface NetworkError {
  readonly kind: NetworkErrorKind;
  /** Human-readable summary for logging/telemetry. */
  readonly message: string;
  /** The underlying thrown value, when one is available. */
  readonly cause?: unknown;
}

/**
 * The result of a dispatch, as a discriminated union.
 *
 * `T` is the shape of a successful gateway run (default {@link GatewayResult}).
 * Callers narrow on `kind`; there is no other legal way to read the payload.
 */
export type DispatchOutcome<T = GatewayResult> =
  | { readonly kind: "ok"; readonly result: T }
  | { readonly kind: "handoff"; readonly status: number; readonly handoff: Handoff }
  | { readonly kind: "error"; readonly status: number; readonly error: GatewayError }
  | { readonly kind: "network"; readonly error: NetworkError };

/** Token usage reported by a completed run. */
export interface Usage {
  readonly prompt: number;
  readonly completion: number;
  readonly total: number;
}

/** One provider attempt within a run step (mirrors the demo trace shape). */
export interface Attempt {
  readonly provider: string;
  readonly error: string | null;
}

/** One turn of the agent loop. */
export interface Step {
  readonly message: string | null;
  readonly usage: number;
  readonly attempts: readonly Attempt[];
}

/** Default success shape returned by the reference `/api/gateway` wrapper. */
export interface GatewayResult {
  readonly final: string | null;
  readonly stop_reason: string;
  readonly complexity: string;
  readonly usage: Usage;
  readonly steps: readonly Step[];
}

/** Zero-argument async supplier of a Firebase App Check token. */
export type AppCheckTokenProvider = () => Promise<string | null>;

/**
 * Zero-argument async supplier of a Firebase Auth ID token.
 *
 * Distinct from {@link AppCheckTokenProvider}: App Check attests the *app*,
 * this attests the *end user* — the wrapper derives the authoritative tenant
 * id (and thus quota isolation) from this token's verified `uid`, not from
 * anything in the request body. See `_lib/auth.py`.
 */
export type AuthTokenProvider = () => Promise<string | null>;

/** Injectable clock/timer seam so retry backoff is deterministic under test. */
export interface Scheduler {
  /** Resolve after `ms` milliseconds. */
  sleep(ms: number): Promise<void>;
  /** Current epoch milliseconds. */
  now(): number;
}
