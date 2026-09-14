/**
 * The one AI model/agent settings screen every app renders identically.
 *
 * Purely presentational and controlled, matching the KeyWizard convention in
 * `templates/vercel-app`: it owns no persistence and knows nothing about
 * `localStorage` or any app's business logic, only `AgentConfig` in and a
 * changed `AgentConfig` out. Wire it to `loadConfig`/`saveConfig` from
 * `@joka-7/modeldispatcher-browser-agent` (or your own store) at the call site.
 */

import { useState } from "react";
import {
  EXTERNAL_CHAT_PROVIDERS,
  openExternalChat,
  PROVIDERS,
  type AgentConfig,
  type ExternalChatProviderId,
  type OpenExternalChatDeps,
  type OpenExternalChatResult,
  type ProviderId,
} from "@joka-7/modeldispatcher-browser-agent";

const DEFAULT_GLOSSARY_URL =
  "https://github.com/joka-7/ModelDispatcher/blob/main/docs/GLOSSARY.md";

export interface ModelPickerProps {
  /** The active BYOK selection. Controlled — this component never mutates it. */
  config: AgentConfig;
  /** Called with the full, updated config on any provider/model/key/URL change. */
  onConfigChange: (config: AgentConfig) => void;
  /** The user's current prompt, carried into the "try it elsewhere" escape
   * hatch so switching to a free chat product doesn't lose their question.
   * Omit to open an empty compose box. */
  question?: string;
  /** Called after `openExternalChat` opens a tab, e.g. to show a toast. */
  onExternalChat?: (result: OpenExternalChatResult) => void;
  /** Where "New to AI agents?" links. Defaults to this project's own glossary. */
  glossaryUrl?: string;
  /** Injected `openExternalChat` deps — for tests or a non-browser host. */
  externalChatDeps?: OpenExternalChatDeps;
}

const PROVIDER_LIST = Object.values(PROVIDERS);
const EXTERNAL_CHAT_LIST = Object.values(EXTERNAL_CHAT_PROVIDERS);

export function ModelPicker({
  config,
  onConfigChange,
  question,
  onExternalChat,
  glossaryUrl = DEFAULT_GLOSSARY_URL,
  externalChatDeps,
}: ModelPickerProps): JSX.Element {
  const [lastExternalChat, setLastExternalChat] = useState<OpenExternalChatResult | null>(null);
  const provider = PROVIDERS[config.provider];

  function handleProviderChange(next: ProviderId): void {
    onConfigChange({
      provider: next,
      apiKey: "",
      model: PROVIDERS[next].defaultModel,
      ollamaUrl: config.ollamaUrl,
    });
  }

  async function handleExternalChat(id: ExternalChatProviderId): Promise<void> {
    const result = await openExternalChat(id, question ?? "", externalChatDeps);
    setLastExternalChat(result);
    onExternalChat?.(result);
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

      <div className="md-external-chat">
        <p className="md-external-chat-lead">No key yet? Try it free in another app instead:</p>
        <div className="md-external-chat-buttons">
          {EXTERNAL_CHAT_LIST.map((p) => (
            <button
              key={p.id}
              type="button"
              className="md-external-chat-btn"
              onClick={() => void handleExternalChat(p.id)}
            >
              {p.name}
            </button>
          ))}
        </div>
        {lastExternalChat && (
          <p className="md-status" role="status">
            Opened {EXTERNAL_CHAT_PROVIDERS[lastExternalChat.provider].name}
            {lastExternalChat.prefilled ? " with your question filled in" : ""}
            {lastExternalChat.copiedToClipboard ? " — also copied to your clipboard." : "."}
          </p>
        )}
      </div>

      <a className="md-glossary-link" href={glossaryUrl} target="_blank" rel="noreferrer">
        New to AI agents? What's a prompt, model, or API key?
      </a>
    </div>
  );
}
