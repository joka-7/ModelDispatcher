# modeldispatcher-react-ui

Three React components for the AI settings screen every one of your apps
needs and has been building separately — split along lines that matter:
**picking a preference is not the same thing as acting on it, and asking a
question is not the same thing as getting a usable answer back.**

- **`ModelPicker`** — a pure settings screen. Add one or more providers, a
  model picked from a curated list per provider, and one or more pooled
  API keys per provider — plus saving a favorite free AI app for later.
  Nothing in it ever navigates — clicking an option in Settings should
  never itself open a new tab.
- **`AskExternallyButton`** — the action that actually opens the saved
  favorite. It belongs wherever the user is composing a question (next to
  the prompt box), not on the settings screen — so clicking it is an
  expected "do something now" button, not a surprise redirect from a
  preferences page.
- **`PasteExternalReply`** — the missing link after `AskExternallyButton`:
  once that opens a tab, there's no API call at all, so nothing can be
  parsed automatically. This captures whatever the user pastes back and
  hands it to your app raw — it has no opinion on JSON or any other
  format, so an app expecting a specific structure (e.g. AppMyTrip parsing
  an itinerary, StepByLearn parsing a lesson plan) does its own parsing on
  what comes out, the same way it already builds its own format
  instructions into the question it hands to `openExternalChat`.

Built on top of [`modeldispatcher-browser-agent`](../browser-agent) —
these are purely the visual layer over that package's provider registry,
model shortlist, favorite-preference storage, and fallback dispatch, so the
two stay in lockstep.

**`ModelPicker`** — add providers, each with a model picked from a list and
one or more pooled keys, plus saving a favorite. Nothing below opens
anything:

![ModelPicker settings screen showing two configured provider cards — Anthropic Claude with a model dropdown and two pooled API keys, and Groq marked with a free badge and one key — an "Add provider" row below them, and a dashed box for saving Claude as a favorite free AI app, with a note that picking one never opens anything](./screenshots/settings.png)

**`AskExternallyButton`** — rendered separately, wherever a question is
actually being asked. This is the only thing that opens a tab:

![AskExternallyButton: a pill-shaped "Ask Claude" button, with a status line below it reading "Opened Claude with your question filled in — also copied to your clipboard."](./screenshots/action.png)

## Why

StepByLearn, JobFlowTracker, KanDOne, and HighFive each ended up with their
own hand-built "AI settings" screen — same fields, different markup, subtly
different behaviour. `browser-agent` already fixed the *logic* duplication
(one provider registry, one `openExternalChat`). This package fixes the *UI*
duplication: one `<ModelPicker>` and one `<AskExternallyButton>`, so a new
app looks like the others from day one and a design change ships to every
app that imports it.

## Install

```bash
npm install modeldispatcher-react-ui
```

(Published to the public npm registry, same as the other ModelDispatcher
client packages — no `.npmrc` or token needed.)

## Usage

```tsx
import { useState } from "react";
import {
  loadConfig,
  saveConfig,
  loadExternalChatFavorite,
  saveExternalChatFavorite,
  complete,
} from "modeldispatcher-browser-agent";
import { ModelPicker, AskExternallyButton, PasteExternalReply } from "modeldispatcher-react-ui";
import "modeldispatcher-react-ui/styles.css";

// Settings screen — nothing here ever navigates. config.providers is a
// fallback LIST: add Gemini, Groq, Anthropic, whatever, each with its own
// pooled key(s) — complete()/streamChat() from browser-agent try them in
// order automatically.
function AiSettings() {
  const [config, setConfig] = useState(loadConfig);
  const [favorite, setFavorite] = useState(loadExternalChatFavorite);

  return (
    <ModelPicker
      config={config}
      onConfigChange={(next) => {
        setConfig(next);
        saveConfig(next);
      }}
      externalChatFavorite={favorite}
      onExternalChatFavoriteChange={(next) => {
        setFavorite(next);
        saveExternalChatFavorite(next);
      }}
    />
  );
}

// Wherever the user actually composes a question — a chat box, a prompt
// field, wherever. This is the one place that opens anything. Baking your
// own format instruction into `question` (and parsing PasteExternalReply's
// raw text the same way) is entirely your app's job — these components
// don't know or care what shape you asked for.
function PromptBar({ tripDetails }: { tripDetails: string }) {
  const [favorite] = useState(loadExternalChatFavorite);
  const question = `${tripDetails}\n\nRespond with ONLY JSON: [{"day": number, "title": string, "activities": string[]}]`;

  return (
    <div>
      {/* ...your textarea/send button... */}
      <AskExternallyButton favorite={favorite} question={question} />
      <PasteExternalReply
        label="No key? Paste what it replied with below."
        onApply={(rawText) => {
          try {
            updateItinerary(JSON.parse(rawText)); // your own parsing/validation
          } catch {
            showError("That didn't look like the JSON we asked for — try pasting the full reply.");
          }
        }}
      />
    </div>
  );
}

// Actually dispatching a request elsewhere in the app — no picker UI
// involved, just the config it produced:
async function ask(question: string) {
  return complete(loadConfig(), question); // tries every configured provider/key in order
}
```

Both components are controlled and stateless about persistence, the same
way `templates/vercel-app`'s `KeyWizard` is: they render props and call
callbacks with the full next value; wiring to `localStorage` (via
`loadConfig`/`saveConfig`/`loadExternalChatFavorite`/`saveExternalChatFavorite`)
or your own store happens at the call site.

### `ModelPicker` props

| Prop | Type | Required | Purpose |
| --- | --- | --- | --- |
| `config` | `AgentConfig` | yes | The active fallback list (`{ providers: ProviderCredential[], ollamaUrl }`) — see [`browser-agent`](../browser-agent) for the shape. |
| `onConfigChange` | `(config: AgentConfig) => void` | yes | Called with the full updated config on any add/remove/edit. |
| `externalChatFavorite` | `ExternalChatProviderId \| null` | yes | The saved "ask externally" favorite, or `null`. |
| `onExternalChatFavoriteChange` | `(favorite: ExternalChatProviderId \| null) => void` | yes | Called when the user picks or clears a favorite. Persist it yourself — this only reports the choice. |
| `glossaryUrl` | `string` | no | Where "New to AI agents?" links. Defaults to this repo's interactive, trilingual [`docs/ai-glossary.html`](../../docs/ai-glossary.html). |

Each provider card lets the user pick a model from `MODEL_OPTIONS` (a
curated shortlist per vendor, from `browser-agent`), add/remove pooled API
keys (or a single URL field for Ollama, which needs none), and remove the
whole provider. An "Add provider" row below the cards offers only the
vendors not already configured.

### `AskExternallyButton` props

| Prop | Type | Required | Purpose |
| --- | --- | --- | --- |
| `favorite` | `ExternalChatProviderId \| null` | yes | The saved favorite. Renders nothing when `null` — there's nothing to ask. |
| `question` | `string` | no | Current prompt, carried into the opened product. |
| `onExternalChat` | `(result: OpenExternalChatResult) => void` | no | Called after a click opens a tab — e.g. to show your own toast. |
| `externalChatDeps` | `OpenExternalChatDeps` | no | Injected `window.open`/clipboard, for tests or a non-browser host. |

### `PasteExternalReply` props

| Prop | Type | Required | Purpose |
| --- | --- | --- | --- |
| `onApply` | `(rawText: string) => void` | yes | Called with the trimmed, unmodified pasted text when the user clicks apply. Parsing/validating it against whatever format you asked for is entirely your own job — this component never inspects it. The textarea clears after the call. |
| `label` | `string` | no | Text above the textarea. |
| `placeholder` | `string` | no | Placeholder text in the empty textarea. |
| `applyLabel` | `string` | no | Apply button text. |

## What's in scope, what isn't

This package owns rendering and layout only. It has no opinion on state
management, persistence, or theming beyond the optional default stylesheet
(`md-*` class names, safe to override or ignore entirely). It does not know
about any app's prompts or business logic — same boundary `browser-agent`
already draws. It also enforces one rule at the component boundary:
`ModelPicker` has no way to call `openExternalChat` even internally — that
action only exists in `AskExternallyButton`, so it can't accidentally end up
back on a settings screen. Same boundary applies to `PasteExternalReply`:
it has no notion of JSON, schemas, or any other output shape — it only
captures and returns raw text, so it never needs updating as different
apps ask their external agent for different structures.

## Testing

```bash
npm run typecheck
npm test
```

Tests render with `react-dom/client` directly against `jsdom` (no
`@testing-library` dependency) and mock `openExternalChat`'s `window.open`/
clipboard the same way `browser-agent`'s own tests do — no real network, no
real API key needed.
