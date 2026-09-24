/**
 * The one AI model/agent settings screen every app renders identically.
 *
 * Purely presentational and controlled, matching the KeyWizard convention in
 * `templates/vercel-app`: it owns no persistence and knows nothing about
 * `localStorage` or any app's business logic, only `AgentConfig` in and a
 * changed `AgentConfig` out. Wire it to `loadConfig`/`saveConfig` from
 * `modeldispatcher-browser-agent` (or your own store) at the call site.
 *
 * `config.providers` is a fallback *list*, not a single selection: add more
 * than one provider (and pool more than one key per provider) and the
 * dispatcher tries each in order, falling back automatically. Settings
 * only: nothing rendered here ever navigates or calls `openExternalChat`.
 * Picking a favorite free AI app just saves *which* product the user would
 * reach for — the button that actually opens it belongs wherever the user
 * is composing a question, via {@link AskExternallyButton}, not here.
 */

import { useState } from "react";
import {
  EXTERNAL_CHAT_PROVIDERS,
  modelOptionsFor,
  PROVIDERS,
  type AgentConfig,
  type ExternalChatProviderId,
  type ProviderCredential,
  type ProviderId,
} from "modeldispatcher-browser-agent";
import { dirFor, resolveStrings, type Locale } from "./i18n.js";

const DEFAULT_GLOSSARY_URL = "https://joka-7.github.io/ModelDispatcher/ai-glossary.html";

export interface ModelPickerProps {
  /** The active fallback list. Controlled — this component never mutates it. */
  config: AgentConfig;
  /** Called with the full, updated config on any provider/model/key/URL change. */
  onConfigChange: (config: AgentConfig) => void;
  /** The saved "ask externally" favorite, or `null` if none is picked yet
   * (see `loadExternalChatFavorite` in `modeldispatcher-browser-agent`). */
  externalChatFavorite: ExternalChatProviderId | null;
  /** Called when the user picks or clears a favorite. Persist it yourself
   * (e.g. with `saveExternalChatFavorite`) — this component only reports the
   * choice and never opens anything itself. */
  onExternalChatFavoriteChange: (favorite: ExternalChatProviderId | null) => void;
  /** Where "New to AI agents?" links. Defaults to this project's own glossary. */
  glossaryUrl?: string;
  /** UI language for this component's own labels/buttons/hints. Provider
   * names and their info links stay in English regardless (see `i18n.ts`).
   * Defaults to English. Hebrew renders the picker's own markup `dir="rtl"`. */
  locale?: Locale;
}

const PROVIDER_LIST = Object.values(PROVIDERS);
const EXTERNAL_CHAT_LIST = Object.values(EXTERNAL_CHAT_PROVIDERS);

function replaceProvider(
  config: AgentConfig,
  index: number,
  patch: Partial<ProviderCredential>,
): AgentConfig {
  return { ...config, providers: config.providers.map((p, i) => (i === index ? { ...p, ...patch } : p)) };
}

function replaceKey(config: AgentConfig, providerIndex: number, keyIndex: number, value: string): AgentConfig {
  return {
    ...config,
    providers: config.providers.map((p, i) =>
      i === providerIndex ? { ...p, apiKeys: p.apiKeys.map((k, ki) => (ki === keyIndex ? value : k)) } : p,
    ),
  };
}

function addKey(config: AgentConfig, providerIndex: number): AgentConfig {
  return {
    ...config,
    providers: config.providers.map((p, i) => (i === providerIndex ? { ...p, apiKeys: [...p.apiKeys, ""] } : p)),
  };
}

function removeKey(config: AgentConfig, providerIndex: number, keyIndex: number): AgentConfig {
  return {
    ...config,
    providers: config.providers.map((p, i) =>
      i === providerIndex ? { ...p, apiKeys: p.apiKeys.filter((_, ki) => ki !== keyIndex) } : p,
    ),
  };
}

function removeProvider(config: AgentConfig, index: number): AgentConfig {
  return { ...config, providers: config.providers.filter((_, i) => i !== index) };
}

function addProvider(config: AgentConfig, provider: ProviderId): AgentConfig {
  const info = PROVIDERS[provider];
  const credential: ProviderCredential = { provider, model: info.defaultModel, apiKeys: info.noKey ? [] : [""] };
  return { ...config, providers: [...config.providers, credential] };
}

export function ModelPicker({
  config,
  onConfigChange,
  externalChatFavorite,
  onExternalChatFavoriteChange,
  glossaryUrl = DEFAULT_GLOSSARY_URL,
  locale = "en",
}: ModelPickerProps): JSX.Element {
  const [pendingProvider, setPendingProvider] = useState<ProviderId | "">("");
  const availableProviders = PROVIDER_LIST.filter(
    (p) => !config.providers.some((cred) => cred.provider === p.id),
  );
  const s = resolveStrings(locale).picker;

  function handleAddProvider(): void {
    if (!pendingProvider) return;
    onConfigChange(addProvider(config, pendingProvider));
    setPendingProvider("");
  }

  return (
    <div className="md-picker" dir={dirFor(locale)}>
      <p className="md-lead">{s.intro}</p>

      {config.providers.length === 0 && <p className="md-empty-state">{s.emptyState}</p>}

      {config.providers.map((cred, index) => {
        const info = PROVIDERS[cred.provider];
        return (
          <div className="md-provider-card" key={cred.provider}>
            <div className="md-provider-card-head">
              <span className="md-provider-name">
                {info.name}
                {info.free && <span className="md-badge md-badge-free">free</span>}
                {info.noKey && <span className="md-badge md-badge-nokey">no key</span>}
              </span>
              <button
                type="button"
                className="md-remove-btn"
                aria-label={s.removeProviderLabel(info.name)}
                onClick={() => onConfigChange(removeProvider(config, index))}
              >
                ×
              </button>
            </div>

            <div className="md-field">
              <label htmlFor={`md-model-${cred.provider}`}>{s.modelLabel}</label>
              <select
                id={`md-model-${cred.provider}`}
                className="md-select"
                value={cred.model}
                onChange={(event) => onConfigChange(replaceProvider(config, index, { model: event.target.value }))}
              >
                {modelOptionsFor(cred.provider).map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </div>

            {info.noKey ? (
              <div className="md-field">
                <label htmlFor="md-ollama-url">{s.urlLabel(info.name)}</label>
                <input
                  id="md-ollama-url"
                  className="md-input"
                  type="text"
                  placeholder={info.placeholder}
                  value={config.ollamaUrl}
                  onChange={(event) => onConfigChange({ ...config, ollamaUrl: event.target.value })}
                />
              </div>
            ) : (
              <div className="md-field">
                <label>{s.apiKeyLabel(info.name, cred.apiKeys.length)}</label>
                <div className="md-key-list">
                  {cred.apiKeys.map((key, keyIndex) => (
                    <div className="md-key-row" key={keyIndex}>
                      <input
                        className="md-input"
                        type="password"
                        autoComplete="off"
                        placeholder={info.placeholder}
                        value={key}
                        onChange={(event) => onConfigChange(replaceKey(config, index, keyIndex, event.target.value))}
                      />
                      <button
                        type="button"
                        className="md-remove-btn md-remove-btn-small"
                        aria-label={s.removeKeyLabel(info.name)}
                        onClick={() => onConfigChange(removeKey(config, index, keyIndex))}
                      >
                        ×
                      </button>
                    </div>
                  ))}
                </div>
                <div className="md-key-actions">
                  <button type="button" className="md-link-btn" onClick={() => onConfigChange(addKey(config, index))}>
                    {cred.apiKeys.length === 0 ? s.addKey : s.addAnotherKey}
                  </button>
                  <a className="md-help-link" href={info.infoUrl} target="_blank" rel="noreferrer">
                    {info.infoText}
                  </a>
                </div>
              </div>
            )}
          </div>
        );
      })}

      {availableProviders.length > 0 && (
        <div className="md-add-provider">
          <select
            className="md-select"
            aria-label={s.chooseProviderAriaLabel}
            value={pendingProvider}
            onChange={(event) => setPendingProvider(event.target.value as ProviderId | "")}
          >
            <option value="">{s.chooseProviderPlaceholder}</option>
            {availableProviders.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
                {p.free ? s.freeSuffix : ""}
              </option>
            ))}
          </select>
          <button type="button" className="md-add-btn" disabled={!pendingProvider} onClick={handleAddProvider}>
            {s.addProviderButton}
          </button>
        </div>
      )}

      <div className="md-favorite" role="radiogroup" aria-label={s.favoriteGroupAriaLabel}>
        <p className="md-favorite-lead">{s.favoriteLead}</p>
        <div className="md-favorite-options">
          <label className="md-favorite-option">
            <input
              type="radio"
              name="md-external-chat-favorite"
              checked={externalChatFavorite === null}
              onChange={() => onExternalChatFavoriteChange(null)}
            />
            {s.favoriteNone}
          </label>
          {EXTERNAL_CHAT_LIST.map((p) => (
            <label key={p.id} className="md-favorite-option">
              <input
                type="radio"
                name="md-external-chat-favorite"
                checked={externalChatFavorite === p.id}
                onChange={() => onExternalChatFavoriteChange(p.id)}
              />
              {p.name}
            </label>
          ))}
        </div>
        <p className="md-favorite-hint">{s.favoriteHint}</p>
      </div>

      <a className="md-glossary-link" href={glossaryUrl} target="_blank" rel="noreferrer">
        {s.glossaryLinkText}
      </a>
    </div>
  );
}
