/**
 * {@link GatewayClient}: the facade a Vercel frontend calls.
 *
 * It composes the interceptor chain once (App Check → retry → timeout → fetch),
 * then `dispatch` runs a request through it and hands the final response to the
 * {@link decodeOutcome} decoder. Every transport failure is normalised into a
 * `{ kind: "network" }` outcome, so callers only ever `switch` on
 * {@link DispatchOutcome.kind} — no thrown errors escape `dispatch`.
 */

import { GatewayEventBus } from "./events.js";
import { appCheckInterceptor } from "./interceptors/appcheck.js";
import { decodeOutcome } from "./interceptors/handoff.js";
import {
  compose,
  type GatewayRequestConfig,
  type Interceptor,
  type Send,
} from "./interceptors/interceptor.js";
import { type RetryOptions, retryInterceptor } from "./interceptors/retry.js";
import { TimeoutError, timeoutInterceptor } from "./interceptors/timeout.js";
import type {
  AppCheckTokenProvider,
  DispatchOutcome,
  GatewayResult,
  NetworkError,
  NetworkErrorKind,
} from "./types.js";

/** Construction options for {@link GatewayClient}. */
export interface GatewayClientOptions {
  /** Endpoint the wrapper is deployed at. Defaults to `"/api/gateway"`. */
  endpoint?: string;
  /** Per-attempt timeout in milliseconds. Defaults to `15000`. */
  timeoutMs?: number;
  /** Firebase App Check token supplier. Omit to disable the header (dev). */
  appCheckTokenProvider?: AppCheckTokenProvider;
  /** Retry/backoff tuning and injected clock (for tests). */
  retry?: RetryOptions;
  /** Shared event bus; a fresh one is created when omitted. */
  bus?: GatewayEventBus;
  /** Injectable `fetch` (defaults to the global). */
  fetchImpl?: typeof fetch;
}

/** Per-call overrides for {@link GatewayClient.dispatch}. */
export interface DispatchOptions {
  /** Caller cancellation, merged with the internal timeout. */
  signal?: AbortSignal;
  /** Extra headers to merge onto this request. */
  headers?: Record<string, string>;
}

const DEFAULT_ENDPOINT = "/api/gateway";
const DEFAULT_TIMEOUT_MS = 15_000;

function classifyNetworkError(error: unknown): NetworkError {
  if (error instanceof TimeoutError) {
    return { kind: "timeout", message: error.message, cause: error };
  }
  // `fetch` throws a TypeError for DNS/connection failures (offline).
  if (error instanceof TypeError) {
    return { kind: "offline", message: error.message, cause: error };
  }
  const kind: NetworkErrorKind = "unknown";
  const message = error instanceof Error ? error.message : String(error);
  return { kind, message, cause: error };
}

/** Resilient client for the ModelDispatcher gateway endpoint. */
export class GatewayClient {
  /** Event bus other subscribers (e.g. the wizard host) can listen on. */
  readonly bus: GatewayEventBus;

  readonly #endpoint: string;
  readonly #timeoutMs: number;
  readonly #send: Send;

  constructor(options: GatewayClientOptions = {}) {
    this.bus = options.bus ?? new GatewayEventBus();
    this.#endpoint = options.endpoint ?? DEFAULT_ENDPOINT;
    this.#timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;

    const fetchImpl = options.fetchImpl ?? globalThis.fetch;

    const chain: Interceptor[] = [];
    if (options.appCheckTokenProvider) {
      chain.push(appCheckInterceptor(options.appCheckTokenProvider));
    }
    chain.push(retryInterceptor(options.retry ?? {}));
    chain.push(timeoutInterceptor());

    const terminal: Send = (config: GatewayRequestConfig) =>
      fetchImpl(config.url, {
        method: config.method,
        headers: config.headers,
        body: JSON.stringify(config.body),
        ...(config.signal ? { signal: config.signal } : {}),
      });

    this.#send = compose(chain, terminal);
  }

  /**
   * Dispatch a request body to the gateway and return a typed outcome.
   *
   * Never rejects: transport failures surface as `{ kind: "network" }`.
   *
   * @typeParam T - Expected success shape (defaults to {@link GatewayResult}).
   */
  async dispatch<T = GatewayResult>(
    body: unknown,
    options: DispatchOptions = {},
  ): Promise<DispatchOutcome<T>> {
    const config: GatewayRequestConfig = {
      url: this.#endpoint,
      method: "POST",
      headers: { "content-type": "application/json", ...options.headers },
      body,
      timeoutMs: this.#timeoutMs,
      ...(options.signal ? { signal: options.signal } : {}),
    };

    let response: Response;
    try {
      response = await this.#send(config);
    } catch (error) {
      return { kind: "network", error: classifyNetworkError(error) };
    }
    return decodeOutcome<T>(response, this.bus);
  }
}

/** Convenience factory mirroring the constructor. */
export function createGatewayClient(options: GatewayClientOptions = {}): GatewayClient {
  return new GatewayClient(options);
}
