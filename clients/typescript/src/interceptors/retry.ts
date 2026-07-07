/**
 * Retry interceptor with exponential backoff (Policy object pattern).
 *
 * Re-issues the request when the response status is in
 * {@link RetryPolicy.retryableStatuses} — the 5xx family — sleeping
 * `min(maxDelayMs, baseDelayMs * 2 ** attempt)` between tries, optionally with
 * full jitter to avoid a thundering herd. It deliberately does **not** retry
 * `402`/`429`: those are structured quota handoffs that must reach the UI intact,
 * not transient faults to paper over. Transport errors thrown by inner layers
 * (e.g. a timeout) propagate unchanged so the client can classify them.
 */

import type { Scheduler } from "../types.js";
import type { GatewayRequestConfig, Interceptor, Send } from "./interceptor.js";

/** Tunable backoff parameters. */
export interface RetryPolicy {
  /** Maximum *additional* attempts after the first (e.g. `3`). */
  readonly maxRetries: number;
  /** Base delay in milliseconds (e.g. `250`). */
  readonly baseDelayMs: number;
  /** Upper bound on any single backoff sleep. */
  readonly maxDelayMs: number;
  /** Apply full jitter (`random(0, delay)`) when `true`. */
  readonly jitter: boolean;
  /** Statuses worth retrying. Never include `402`/`429`. */
  readonly retryableStatuses: readonly number[];
}

/** Sensible defaults for a Vercel ↔ serverless-Python round trip. */
export const DEFAULT_RETRY_POLICY: RetryPolicy = {
  maxRetries: 3,
  baseDelayMs: 250,
  maxDelayMs: 4_000,
  jitter: true,
  retryableStatuses: [500, 502, 503, 504],
};

/** Real-time scheduler backing the default client. */
export const REAL_SCHEDULER: Scheduler = {
  sleep: (ms: number) => new Promise((resolve) => setTimeout(resolve, ms)),
  now: () => Date.now(),
};

/**
 * Compute the backoff for a given zero-based attempt index.
 *
 * @param policy - The active {@link RetryPolicy}.
 * @param attempt - Number of retries already performed (0 for the first retry).
 * @param random - Source of `[0, 1)` randomness (injected for deterministic tests).
 */
export function backoffDelayMs(
  policy: RetryPolicy,
  attempt: number,
  random: () => number = Math.random,
): number {
  const uncapped = policy.baseDelayMs * 2 ** attempt;
  const capped = Math.min(policy.maxDelayMs, uncapped);
  return policy.jitter ? Math.floor(random() * capped) : capped;
}

/** Options for {@link retryInterceptor}. */
export interface RetryOptions {
  readonly policy?: RetryPolicy;
  readonly scheduler?: Scheduler;
  readonly random?: () => number;
}

/** Build the backoff/retry {@link Interceptor}. */
export function retryInterceptor(options: RetryOptions = {}): Interceptor {
  const policy = options.policy ?? DEFAULT_RETRY_POLICY;
  const scheduler = options.scheduler ?? REAL_SCHEDULER;
  const random = options.random ?? Math.random;

  return {
    async intercept(config: GatewayRequestConfig, next: Send): Promise<Response> {
      let response = await next(config);
      let attempt = 0;

      while (
        policy.retryableStatuses.includes(response.status) &&
        attempt < policy.maxRetries
      ) {
        await scheduler.sleep(backoffDelayMs(policy, attempt, random));
        attempt += 1;
        response = await next(config);
      }

      return response;
    },
  };
}
