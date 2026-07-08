/**
 * Shared {@link GatewayClient} singleton for the reference page.
 *
 * Wires both perimeter guards the wrapper enforces by default: Firebase App
 * Check (attests the app instance) and Firebase Auth (attests the end user —
 * the wrapper derives the authoritative tenant id, and thus quota isolation,
 * from the verified `uid`; see `api/_lib/auth.py`). The reference wiring signs
 * the user in **anonymously** so there's a stable per-browser identity with no
 * login form — swap in a real sign-in flow for a production app.
 *
 * Every Firebase call is deferred until a token is actually requested (i.e.
 * until `gateway.dispatch()` runs in the browser). `createGatewayClient` itself
 * touches no network and needs no Firebase config, so importing this module —
 * including during `next build`'s static analysis — is always safe, even
 * against an empty `.env`.
 */

"use client";

import { createGatewayClient } from "@joka-7/modeldispatcher-client";
import { type FirebaseApp, getApp, getApps, initializeApp } from "firebase/app";
import {
  type AppCheck,
  getToken as getAppCheckToken,
  initializeAppCheck,
  ReCaptchaV3Provider,
} from "firebase/app-check";
import { type Auth, type User, getAuth, signInAnonymously } from "firebase/auth";

function firebaseConfig(): Record<string, string | undefined> {
  return {
    apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
    authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
    projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
    appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
  };
}

let cachedApp: FirebaseApp | null = null;

/** Return the shared Firebase app, initialising it on first use. */
function firebaseApp(): FirebaseApp {
  cachedApp ??= getApps().length ? getApp() : initializeApp(firebaseConfig());
  return cachedApp;
}

let cachedAppCheck: AppCheck | null = null;

/** Return the App Check instance, or `null` when no site key is configured. */
function appCheckInstance(): AppCheck | null {
  const siteKey = process.env.NEXT_PUBLIC_FIREBASE_APPCHECK_SITE_KEY;
  if (!siteKey) return null;
  cachedAppCheck ??= initializeAppCheck(firebaseApp(), {
    provider: new ReCaptchaV3Provider(siteKey),
    isTokenAutoRefreshEnabled: true,
  });
  return cachedAppCheck;
}

let cachedAuth: Auth | null = null;

/** Return the shared Firebase Auth instance, initialising it on first use. */
function authInstance(): Auth {
  cachedAuth ??= getAuth(firebaseApp());
  return cachedAuth;
}

let signInPromise: Promise<User> | null = null;

/**
 * Resolve to a signed-in user, signing in anonymously on first call.
 *
 * Memoised so concurrent dispatches don't race multiple sign-in attempts; a
 * failed attempt clears the memo so the next call can retry.
 */
function ensureSignedIn(): Promise<User> {
  const auth = authInstance();
  if (auth.currentUser) return Promise.resolve(auth.currentUser);
  signInPromise ??= signInAnonymously(auth)
    .then((credential) => credential.user)
    .catch((error: unknown) => {
      signInPromise = null;
      throw error;
    });
  return signInPromise;
}

/**
 * App Check token provider for {@link GatewayClientOptions.appCheckTokenProvider}.
 *
 * Fails soft (`null`) on any error — the wrapper's own `MD_APP_CHECK_MODE`
 * guard is the actual enforcement point; a client-side misconfiguration should
 * degrade to "no header attached" and let the server reject, not throw.
 */
async function appCheckTokenProvider(): Promise<string | null> {
  try {
    const instance = appCheckInstance();
    if (!instance) return null;
    return (await getAppCheckToken(instance)).token;
  } catch {
    return null;
  }
}

/**
 * Auth token provider for {@link GatewayClientOptions.authTokenProvider}.
 *
 * Fails soft (`null`) on any error, matching {@link appCheckTokenProvider} —
 * the wrapper's `MD_AUTH_MODE` guard is the real enforcement point.
 */
async function authTokenProvider(): Promise<string | null> {
  try {
    const user = await ensureSignedIn();
    return await user.getIdToken();
  } catch {
    return null;
  }
}

/** The client every dispatch in this reference app goes through. */
export const gateway = createGatewayClient({
  appCheckTokenProvider,
  authTokenProvider,
});
