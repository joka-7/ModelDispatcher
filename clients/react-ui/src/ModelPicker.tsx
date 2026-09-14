/**
 * The one AI model/agent settings screen every app renders identically.
 *
 * Purely presentational and controlled, matching the KeyWizard convention in
 * `templates/vercel-app`: it owns no persistence and knows nothing about
 * `localStorage` or any app's business logic, only `AgentConfig` in and a
 * changed `AgentConfig` out. Wire it to `loadConfig`/`saveConfig` from
 * `@joka-7/modeldispatcher-browser-agent` (or your own store) at the call site.
 *
 * Settings only: nothing rendered here ever navigates or calls
 * `openExternalChat`. Picking a favorite free AI app just saves *which*
 * product the user would reach for — the button that actually opens it
 * belongs wherever the user is composing a question, via
 * {@link AskExternallyButton}, not on a preferences screen.
 */

import {
  EXTERNAL_CHAT_PROVIDERS,
  PROVIDERS,
  type AgentConfig,
  type ExternalChatProviderId,
  type ProviderId,
} from "@joka-7/modeldispatcher-browser-agent";

const DEFAULT_GLOSSARY_URL =
  "https://github.com/joka-7/ModelDispatcher/blob/main/docs/GLOSSARY.md";

export interface ModelPickerProps {
  /** The active BYOK selection. Controlled — this component never mutates it. */
  config: AgentConfig;
  /** Called with the full, updated config on any provider/model/key/URL change. */
  onConfigChange: (config: AgentConfig) => void;
  /** The saved "ask externally" favorite, or `null` if none is picked yet
   * (see `loadExternalChatFavorite` in `@joka-7/modeldispatcher-browser-agent`). */
  externalChatFavorite: ExternalChatProviderId | null;
  /** Called when the user picks or clears a favorite. Persist it yourself
   * (e.g. with `saveExternalChatFavorite`) — this component only reports the
   * choice and never opens anything itself. */
  onExternalChatFavoriteChange: (favorite: ExternalChatProviderId | null) => void;
  /** Where "New to AI agents?" links. Defaults to this project's own glossary. */
  glossaryUrl?: string;
}

const PROVIDER_LIST = Object.values(PROVIDERS);
const EXTERNAL_CHAT_LIST = Object.values(EXTERNAL_CHAT_PROVIDERS);

export function ModelPicker({
  config,
  onConfigChange,
  externalChatFavorite,
  onExternalChatFavoriteChange,
  glossaryUrl = DEFAULT_GLOSSARY_URL,
}: ModelPickerProps): JSX.Element {
  const provider = PROVIDERS[config.provider];

  function handleProviderChange(next: ProviderId): void {
    onConfigChange({
      provider: next,
      apiKey: "",
      model: PROVIDERS[next].defaultModel,
      ollamaUrl: config.ollamaUrl,
    });
  }

  return (
    <div className="md-picker">
      <div className="md-field">
        <label htmlFor="md-provider">AI provider</label>
        <select
          id="md-provider"
          className="md-select"
          value={config.provider}
          onChange={(event) => handleProviderChange(event.target.value as ProviderId)}
        >
          {PROVIDER_LIST.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
              {p.free ? " (free)" : ""}
            </option>
          ))}
        </select>
      </div>

      <div className="md-field">
        <label htmlFor="md-model">Model</label>
        <input
          id="md-model"
          className="md-input"
          type="text"
          value={config.model}
          onChange={(event) => onConfigChange({ ...config, model: event.target.value })}
        />
      </div>

      {provider.noKey ? (
        <div className="md-field">
          <label htmlFor="md-ollama-url">{provider.name} URL</label>
          <input
            id="md-ollama-url"
            className="md-input"
            type="text"
            placeholder={provider.placeholder}
            value={config.ollamaUrl}
            onChange={(event) => onConfigChange({ ...config, ollamaUrl: event.target.value })}
          />
        </div>
      ) : (
        <div className="md-field">
          <label htmlFor="md-api-key">{provider.name} API key</label>
          <input
            id="md-api-key"
            className="md-input"
            type="password"
            autoComplete="off"
            placeholder={provider.placeholder}
            value={config.apiKey}
            onChange={(event) => onConfigChange({ ...config, apiKey: event.target.value })}
          />
          <a className="md-help-link" href={provider.infoUrl} target="_blank" rel="noreferrer">
            {provider.infoText}
          </a>
        </div>
      )}

      <div className="md-favorite" role="radiogroup" aria-label="Favorite free AI app">
        <p className="md-favorite-lead">Or save a favorite free AI app for later:</p>
        <div className="md-favorite-options">
          <label className="md-favorite-option">
            <input
              type="radio"
              name="md-external-chat-favorite"
              checked={externalChatFavorite === null}
              onChange={() => onExternalChatFavoriteChange(null)}
            />
            None
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
        <p className="md-favorite-hint">
          Just a saved preference — picking one here never opens anything.
        </p>
      </div>

      <a className="md-glossary-link" href={glossaryUrl} target="_blank" rel="noreferrer">
        New to AI agents? What's a prompt, model, or API key?
      </a>
    </div>
  );
}
