/**
 * Timeout interceptor.
 *
 * Arms an {@link AbortController} that fires after `config.timeoutMs`, and also
 * forwards any caller-supplied `config.signal`, so a slow serverless cold-start
 * cannot hang the UI. When the deadline trips it re-labels the resulting
 * `AbortError` as a {@link TimeoutError} (an external cancellation keeps its
 * original error), which the client maps to a `{ kind: "network" }` outcome.
 */

import type { GatewayRequestConfig, Interceptor, Send } from "./interceptor.js";

/** Thrown when a single transport attempt exceeds its deadline. */
export class TimeoutError extends Error {
  constructor(timeoutMs: number) {
    super(`request exceeded ${timeoutMs}ms timeout`);
    this.name = "TimeoutError";
  }
}

/** Build the {@link Interceptor} that enforces a per-attempt deadline. */
export function timeoutInterceptor(): Interceptor {
  return {
    async intercept(config: GatewayRequestConfig, next: Send): Promise<Response> {
      const controller = new AbortController();
      let timedOut = false;
      const timer = setTimeout(() => {
        timedOut = true;
        controller.abort();
      }, config.timeoutMs);

      const external = config.signal;
      if (external) {
        if (external.aborted) controller.abort();
        else external.addEventListener("abort", () => controller.abort(), { once: true });
      }

      try {
        return await next({ ...config, signal: controller.signal });
      } catch (error) {
        if (timedOut) throw new TimeoutError(config.timeoutMs);
        throw error;
      } finally {
        clearTimeout(timer);
      }
    },
  };
}
