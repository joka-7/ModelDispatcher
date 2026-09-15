/**
 * Per-app opt-in/opt-out for the two things this package supplies. This is a
 * developer/deploy-time decision made once when an app is wired up — never a
 * switch an end user sees or controls. Both flags default to enabled, so
 * adopting the shared framework is opt-OUT per app, not opt-in-everywhere.
 *
 * This package never reads environment variables itself: every bundler
 * exposes them differently (`import.meta.env` for Vite, `process.env` for
 * Next.js/CRA), so resolving env vars is left to each app's own config
 * module, which passes the result in as `overrides`.
 */

/** Which parts of the shared framework this app has enabled. */
export interface DispatcherFeatureFlags {
  /** Render `<ModelPicker>`/`<AskExternallyButton>`, or this app's own settings UI. */
  readonly ui: boolean;
  /** Route AI calls through `complete()`/`streamComplete()`'s fallback dispatch,
   * or this app's own existing call path. */
  readonly dispatch: boolean;
}

/** Both features enabled — the framework's out-of-the-box behavior. */
export const DEFAULT_DISPATCHER_FEATURES: DispatcherFeatureFlags = Object.freeze({
  ui: true,
  dispatch: true,
});

/**
 * Resolves the effective feature flags for this app: enabled-by-default,
 * merged with whatever this app's own config module decided to override.
 *
 * Call this once at your app's own composition root and pass the result down
 * to wherever the UI/dispatch branching actually happens — see
 * `docs/USAGE.md` for the full pattern.
 */
export function resolveDispatcherFeatures(
  overrides?: Partial<DispatcherFeatureFlags>,
): DispatcherFeatureFlags {
  return { ...DEFAULT_DISPATCHER_FEATURES, ...overrides };
}
