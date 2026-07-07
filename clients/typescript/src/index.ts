/**
 * `@modeldispatcher/client` — resilient TypeScript client for the
 * ModelDispatcher AI gateway.
 *
 * Public surface: construct a {@link GatewayClient} with
 * {@link createGatewayClient}, `dispatch` request bodies, and `switch` on the
 * returned {@link DispatchOutcome}. React apps use `useGateway` from the
 * `@modeldispatcher/client/react` subpath. All resilience — timeouts, 5xx
 * backoff, and 402/429 key-wizard handoff decoding — is built in.
 */

export { GatewayClient, createGatewayClient } from "./client.js";
export type { GatewayClientOptions, DispatchOptions } from "./client.js";

export { GatewayEventBus } from "./events.js";
export type {
  GatewayEventMap,
  HandoffEvent,
  Listener,
  Unsubscribe,
} from "./events.js";

export { compose } from "./interceptors/interceptor.js";
export type { GatewayRequestConfig, Interceptor, Send } from "./interceptors/interceptor.js";

export { appCheckInterceptor, APP_CHECK_HEADER } from "./interceptors/appcheck.js";
export { timeoutInterceptor, TimeoutError } from "./interceptors/timeout.js";
export {
  retryInterceptor,
  backoffDelayMs,
  DEFAULT_RETRY_POLICY,
  REAL_SCHEDULER,
} from "./interceptors/retry.js";
export type { RetryPolicy, RetryOptions } from "./interceptors/retry.js";
export {
  decodeOutcome,
  isHandoffPayload,
  HANDOFF_ACTIONS,
} from "./interceptors/handoff.js";

export type {
  Attempt,
  AppCheckTokenProvider,
  DispatchOutcome,
  GatewayError,
  GatewayResult,
  Handoff,
  HandoffAction,
  NetworkError,
  NetworkErrorKind,
  Scheduler,
  Step,
  Usage,
} from "./types.js";
