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

## No-API-key escape hatch: `openExternalChat`

For a user with no API key configured (or who just doesn't want to set one
up), `openExternalChat` hands their question off to a free, public AI chat
product instead — ChatGPT, Claude, Gemini (via Google Search's AI Mode), or
Groq — opening it in a new tab with the question pre-filled where the
product supports that, and always copying the question to the clipboard too
as a fallback:

```ts
import { openExternalChat, EXTERNAL_CHAT_PROVIDERS } from "@joka-7/modeldispatcher-browser-agent";

const result = await openExternalChat("claude", "Summarise this in one sentence: ...");
// result.prefilled        — true if the question actually made it into the URL
// result.copiedToClipboard — true if it's also on the clipboard, for pasting
```

`EXTERNAL_CHAT_PROVIDERS` lists the four supported products for rendering a
picker, the same way `PROVIDERS` does for the BYOK providers above.

**Why this needs a clipboard fallback at all:** the URL query parameters that
pre-fill a provider's chat box (`claude.ai/new?q=...`, `chatgpt.com/?q=...`,
Google Search's `udm=50` AI Mode) are undocumented, reverse-engineered
conventions — not a stable API any vendor promises to keep working. Groq has
no known one at all, so it just opens the plain homepage. `openExternalChat`
always copies the question to the clipboard regardless, so a broken or
removed parameter never means the user's question is lost, just that they
paste instead of finding it already typed in.

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

All 58 tests run against mocked `fetch`/`ReadableStream`/`window.open`/
clipboard — no real network, no real API key needed.
