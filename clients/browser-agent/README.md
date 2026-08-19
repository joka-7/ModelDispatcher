# @joka-7/modeldispatcher-browser-agent

A browser-native, bring-your-own-key AI agent core. The client-side sibling
to `model-dispatcher` for apps with **no backend** to run the Python gateway
on: talks directly to Gemini, OpenAI, Anthropic, Groq, or a local Ollama from
the browser, using whatever key the end user supplies. No vendor SDK, no
server, nothing sent anywhere but the provider itself.

Extracted from four apps (StepByLearn, JobFlowTracker, KanDOne, HighFive)
that had each independently built the same thing — one canonical provider
registry, request/response handling, and streaming parser instead of four
near-duplicate copies.

## Install

```bash
npm install @joka-7/modeldispatcher-browser-agent
```

(Published to GitHub Packages — needs a `.npmrc` with
`@joka-7:registry=https://npm.pkg.github.com` and a `read:packages` token.)

## Usage

```ts
import { loadConfig, complete, streamChat, PROVIDERS } from "@joka-7/modeldispatcher-browser-agent";

// Reads aiProvider/aiApiKey/aiModel/ollamaUrl from localStorage by default;
// pass a ConfigStorage + ConfigKeys to use your app's own key names.
const cfg = loadConfig();

// One-shot, full text back:
const answer = await complete(cfg, "Summarise this in one sentence: ...");

// One-shot, incremental text back:
await streamComplete(cfg, "Write a haiku", { onChunk: (text) => render(text) });

// Multi-turn chat — normalises a raw UI message list (role validation,
// user-first ordering, merging) before dispatching:
await streamChat(cfg, uiMessages, {
  systemInstruction: "You are a helpful assistant.",
  onChunk: (text) => render(text),
});
```

`PROVIDERS` is the canonical registry (name, default model, key placeholder,
where to get a key) for rendering a settings picker — the same shape every
app's `APIKeySettings`/`Settings` screen already builds by hand.

## What's in scope, what isn't

This package owns the generic "talk to a provider" plumbing: provider
configs, request/response translation, SSE/NDJSON stream parsing, retry on
429/5xx, timeout/abort handling, Ollama URL validation, and chat-history
normalisation. It deliberately does **not** know about any app's actual
prompts or business logic (job-search coaching, trip parsing, whatever) —
that stays in each app, calling through this the same way
`services/llm_model_dispatcher.py` in AppMyTrip calls through the Python
gateway without the gateway knowing what a "trip" is.

## Testing

```bash
npm run typecheck
npm test
```

All 48 tests run against mocked `fetch`/`ReadableStream` — no real network,
no real API key needed.
