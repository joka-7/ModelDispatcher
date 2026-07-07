/**
 * Interceptor pipeline contracts (Chain of Responsibility).
 *
 * Each {@link Interceptor} receives the outgoing request config and a `next`
 * continuation. It may mutate the config, short-circuit, wrap `next` with
 * cross-cutting behaviour (timeout, retry), and inspect the resulting response
 * before returning it. Interceptors are composed as an onion: the first in the
 * list is the outermost layer.
 */

/** The in-flight request description handed down the interceptor chain. */
export interface GatewayRequestConfig {
  /** Absolute or app-relative endpoint, e.g. `"/api/gateway"`. */
  url: string;
  /** HTTP method; the gateway endpoint is `POST`. */
  method: string;
  /** Mutable header bag; interceptors add to it (App Check, content-type). */
  headers: Record<string, string>;
  /** JSON-serialisable request body. */
  body: unknown;
  /** Per-attempt timeout in milliseconds. */
  timeoutMs: number;
  /** Optional caller-supplied cancellation signal, merged with the timeout. */
  signal?: AbortSignal;
}

/** Terminal continuation: performs exactly one transport attempt. */
export type Send = (config: GatewayRequestConfig) => Promise<Response>;

/** A single layer of the request/response pipeline. */
export interface Interceptor {
  /**
   * Process the request and return a response.
   *
   * @param config - The (mutable) request configuration.
   * @param next - Continuation invoking the remaining inner layers.
   */
  intercept(config: GatewayRequestConfig, next: Send): Promise<Response>;
}

/**
 * Fold a list of interceptors around a terminal {@link Send} into one `Send`.
 *
 * The first interceptor becomes the outermost layer, so a list of
 * `[appcheck, retry, timeout]` yields `appcheck(retry(timeout(fetch)))` — retry
 * re-drives the timeout+transport on each attempt.
 */
export function compose(interceptors: readonly Interceptor[], terminal: Send): Send {
  return interceptors.reduceRight<Send>(
    (next, interceptor) => (config) => interceptor.intercept(config, next),
    terminal,
  );
}
