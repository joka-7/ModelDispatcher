/**
 * Firebase Auth interceptor (request side).
 *
 * Mints/attaches the ID token the Vercel Python wrapper verifies to derive an
 * *authoritative* tenant id (see `_lib/auth.py`). Mirrors
 * {@link appCheckInterceptor} exactly: the token provider is injected rather
 * than importing the Firebase SDK directly, so this package carries no hard
 * Firebase dependency. Without this header, the wrapper's `MD_AUTH_MODE=enforce`
 * default rejects the request with `401` before the gateway ever runs.
 */

import type { AuthTokenProvider } from "../types.js";
import type { GatewayRequestConfig, Interceptor, Send } from "./interceptor.js";

/** HTTP header the wrapper reads the bearer token from. */
export const AUTHORIZATION_HEADER = "Authorization";

/**
 * Build the interceptor that stamps every request with a Firebase Auth ID token.
 *
 * A `null` token (provider opted out, or dev bypass) is simply not attached;
 * the wrapper then decides whether to reject based on its own `MD_AUTH_MODE`.
 */
export function authInterceptor(provider: AuthTokenProvider): Interceptor {
  return {
    async intercept(config: GatewayRequestConfig, next: Send): Promise<Response> {
      const token = await provider();
      if (token) {
        config.headers[AUTHORIZATION_HEADER] = `Bearer ${token}`;
      }
      return next(config);
    },
  };
}
