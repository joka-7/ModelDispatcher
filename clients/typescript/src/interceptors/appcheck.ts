/**
 * Firebase App Check interceptor (request side).
 *
 * Mints/attaches the attestation token the Vercel Python wrapper verifies before
 * it will invoke the gateway. The token *provider* is injected rather than
 * importing the Firebase SDK directly, so this package carries no hard Firebase
 * dependency and stays trivially testable — the app wires
 * `() => getToken(appCheck).then(r => r.token)` at construction time.
 */

import type { AppCheckTokenProvider } from "../types.js";
import type { GatewayRequestConfig, Interceptor, Send } from "./interceptor.js";

/** HTTP header the wrapper reads (matches `firebase_admin.app_check`). */
export const APP_CHECK_HEADER = "X-Firebase-AppCheck";

/**
 * Build the interceptor that stamps every request with an App Check token.
 *
 * A `null` token (provider opted out, or dev bypass) is simply not attached;
 * the wrapper then decides whether to reject based on its own environment.
 */
export function appCheckInterceptor(provider: AppCheckTokenProvider): Interceptor {
  return {
    async intercept(config: GatewayRequestConfig, next: Send): Promise<Response> {
      const token = await provider();
      if (token) {
        config.headers[APP_CHECK_HEADER] = token;
      }
      return next(config);
    },
  };
}
