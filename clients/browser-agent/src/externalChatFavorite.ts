/**
 * Persistence for a visitor's saved "ask externally" favorite.
 *
 * Deliberately separate from {@link ./config.js}'s `AgentConfig`
 * (provider/key/model for BYOK dispatch): picking a favorite here means the
 * visitor wants the app to offer opening this free chat product instead of
 * calling any API, so it has nothing to do with which provider/key is
 * configured for BYOK and must never be conflated with it. A settings screen
 * showing both is choosing between two independent, saveable preferences —
 * selecting a favorite here never itself opens anything (see
 * {@link ./externalChat.js}'s `openExternalChat` for the action that does).
 */

import { EXTERNAL_CHAT_PROVIDERS } from "./externalChat.js";
import { resolveStorage, type ConfigStorage } from "./config.js";
import type { ExternalChatProviderId } from "./types.js";

export const DEFAULT_EXTERNAL_CHAT_FAVORITE_KEY = "aiExternalChatFavorite";

function isKnownExternalChatProvider(id: string): id is ExternalChatProviderId {
  return Object.hasOwn(EXTERNAL_CHAT_PROVIDERS, id);
}

/** Read the saved favorite, or `null` if none is set (or the stored value is
 * no longer a recognised provider). */
export function loadExternalChatFavorite(
  storage?: ConfigStorage,
  key: string = DEFAULT_EXTERNAL_CHAT_FAVORITE_KEY,
): ExternalChatProviderId | null {
  const raw = resolveStorage(storage).getItem(key);
  return raw !== null && isKnownExternalChatProvider(raw) ? raw : null;
}

/** Persist the favorite; pass `null` to clear it. */
export function saveExternalChatFavorite(
  favorite: ExternalChatProviderId | null,
  storage?: ConfigStorage,
  key: string = DEFAULT_EXTERNAL_CHAT_FAVORITE_KEY,
): void {
  const store = resolveStorage(storage);
  if (favorite === null) store.removeItem(key);
  else store.setItem(key, favorite);
}
