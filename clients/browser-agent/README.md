# @joka-7/modeldispatcher-browser-agent

A browser-native, bring-your-own-key AI agent core. The client-side sibling
to `model-dispatcher` for apps with **no backend** to run the Python gateway
on: talks directly to Gemini, OpenAI, Anthropic, Groq, or a local Ollama from
the browser, using whatever key(s) the end user supplies. No vendor SDK, no
server, nothing sent anywhere but the provider itself.

`AgentConfig` is a **fallback list**, not a single selection: configure more
than one provider (and more than one pooled key per provider), and
`complete`/`streamComplete`/`streamChat` try each candidate in order,
falling through to the next key or provider on failure instead of failing
the whole request — the same idea as the Python core's fallback chain,
running client-side.

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
import { loadConfig, complete, streamChat, PROVIDERS, MODEL_OPTIONS } from "@joka-7/modeldispatcher-browser-agent";

// Reads the whole fallback list from localStorage by default (one JSON
// blob under "aiConfig"); pass a ConfigStorage + ConfigKeys to use your
// app's own key name.
const cfg = loadConfig();
// cfg.providers: [{ provider: "gemini", model: "gemini-2.0-flash", apiKeys: ["AIza-..."] }, ...]
// cfg.ollamaUrl: "http://localhost:11434"

// One-shot, full text back — tries cfg.providers in order, and each
// provider's own pooled keys in order, until one succeeds:
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
where to get a key) and `MODEL_OPTIONS`/`modelOptionsFor(id)` a curated
shortlist of current models per vendor — together enough to render a
provider `<select>` and a model `<select>`, the same shape every app's
`APIKeySettings`/`Settings` screen already builds by hand.

### Fallback errors

```ts
import { NoProviderConfiguredError, AllProvidersExhaustedError } from "@joka-7/modeldispatcher-browser-agent";

try {
  await complete(cfg, prompt);
} catch (err) {
  if (err instanceof NoProviderConfiguredError) {
    // cfg.providers has nothing usable — send the visitor to AI settings.
  } else if (err instanceof AllProvidersExhaustedError) {
    // Every configured provider/key was tried. err.attempts is
    // [{ provider, error }, ...] for a detailed failure message.
  } else {
    throw err;
  }
}
```

A streaming call (`streamComplete`/`streamChat`) only falls back **before**
the first chunk of a given candidate reaches `onChunk`. Once any text has
streamed, a later failure on that same candidate is thrown immediately
instead of silently retried on the next provider — the caller has already
rendered a partial answer, and switching providers mid-stream would
duplicate or contradict it rather than complete it.

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

## Saving a favorite for the escape hatch: `loadExternalChatFavorite`

`openExternalChat` is an *action* — it navigates the instant it's called, so
it belongs on a button next to wherever the user is actually about to ask
something, never inside a settings screen (clicking a settings option should
never itself open a new tab). What *does* belong in settings is letting the
visitor pick and save **which** free product they'd reach for, ahead of
time — that's what this is for:

```ts
import {
  loadExternalChatFavorite,
  saveExternalChatFavorite,
} from "@joka-7/modeldispatcher-browser-agent";

// Settings screen: save the pick. No network call, no navigation.
saveExternalChatFavorite("claude");

// Wherever the user composes a question: read it back to decide what
// the "ask externally" button should say/do.
const favorite = loadExternalChatFavorite(); // "claude" | null
if (favorite) {
  await openExternalChat(favorite, currentQuestion);
}
```

Deliberately separate storage from `loadConfig`/`saveConfig` (BYOK
provider/key/model) — picking a favorite here has nothing to do with which
BYOK provider is configured, and a settings screen commonly offers both as
independent, unrelated choices.

## What's in scope, what isn't

This package owns the generic "talk to a provider" plumbing: provider
configs, request/response translation, SSE/NDJSON stream parsing, retry on
429/5xx, cross-provider/cross-key fallback dispatch, timeout/abort handling,
Ollama URL validation, and chat-history normalisation. It deliberately does
**not** know about any app's actual
prompts or business logic (job-search coaching, trip parsing, whatever) —
that stays in each app, calling through this the same way
`services/llm_model_dispatcher.py` in AppMyTrip calls through the Python
gateway without the gateway knowing what a "trip" is.

## Testing

```bash
npm run typecheck
npm test
```

All 75 tests run against mocked `fetch`/`ReadableStream`/`window.open`/
clipboard — no real network, no real API key needed.
