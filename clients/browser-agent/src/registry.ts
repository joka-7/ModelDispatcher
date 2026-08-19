/**
 * The provider registry — one canonical source for the metadata every app's
 * settings screen was independently duplicating (name, default model, key
 * placeholder, where to get a key).
 */

import type { ProviderId, ProviderInfo } from "./types.js";

export const PROVIDERS: Record<ProviderId, ProviderInfo> = {
  gemini: {
    id: "gemini",
    name: "Google Gemini",
    free: false,
    defaultModel: "gemini-2.0-flash",
    placeholder: "AIza...",
    infoUrl: "https://aistudio.google.com/app/apikey",
    infoText: "Get a free key from Google AI Studio",
  },
  groq: {
    id: "groq",
    name: "Groq",
    free: true,
    defaultModel: "llama-3.1-8b-instant",
    placeholder: "gsk_...",
    infoUrl: "https://console.groq.com/keys",
    infoText: "Get a free key from Groq Console",
  },
  ollama: {
    id: "ollama",
    name: "Ollama (local)",
    free: true,
    noKey: true,
    defaultModel: "llama3.2",
    placeholder: "http://localhost:11434",
    infoUrl: "https://ollama.ai",
    infoText: "Install Ollama on your machine",
  },
  anthropic: {
    id: "anthropic",
    name: "Anthropic Claude",
    free: false,
    defaultModel: "claude-haiku-4-5-20251001",
    placeholder: "sk-ant-...",
    infoUrl: "https://console.anthropic.com/settings/keys",
    infoText: "Get a key from the Anthropic Console",
  },
  openai: {
    id: "openai",
    name: "OpenAI",
    free: false,
    defaultModel: "gpt-4o-mini",
    placeholder: "sk-...",
    infoUrl: "https://platform.openai.com/api-keys",
    infoText: "Get a key from the OpenAI Platform",
  },
};

export function isKnownProvider(id: string): id is ProviderId {
  return Object.hasOwn(PROVIDERS, id);
}
