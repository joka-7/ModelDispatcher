# @joka-7/modeldispatcher-react-ui

Two React components for the AI settings screen every one of your apps
needs and has been building separately — split along a line that matters:
**picking a preference is not the same thing as acting on it.**

- **`ModelPicker`** — a pure settings screen. Provider/model/key, or saving
  a favorite free AI app for later. Nothing in it ever navigates — clicking
  an option in Settings should never itself open a new tab.
- **`AskExternallyButton`** — the action that actually opens the saved
  favorite. It belongs wherever the user is composing a question (next to
  the prompt box), not on the settings screen — so clicking it is an
  expected "do something now" button, not a surprise redirect from a
  preferences page.

Built on top of [`@joka-7/modeldispatcher-browser-agent`](../browser-agent) —
these are purely the visual layer over that package's provider registry,
favorite-preference storage, and `openExternalChat` escape hatch, so the two
stay in lockstep.

**`ModelPicker`** — provider/model/key, plus saving a favorite. Nothing
below opens anything:

![ModelPicker settings screen: a provider dropdown set to Anthropic Claude, a model field, a masked API key field with a "Get a key" link, and a dashed box offering to save Claude as a favorite free AI app via radio buttons, with a note that picking one never opens anything](./screenshots/settings.png)

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
npm install @joka-7/modeldispatcher-react-ui
```

(Published to GitHub Packages, same as the other `@joka-7` client packages —
needs a `.npmrc` with `@joka-7:registry=https://npm.pkg.github.com` and a
`read:packages` token.)

## Usage

```tsx
import { useState } from "react";
import {
  loadConfig,
  saveConfig,
  loadExternalChatFavorite,
  saveExternalChatFavorite,
} from "@joka-7/modeldispatcher-browser-agent";
import { ModelPicker, AskExternallyButton } from "@joka-7/modeldispatcher-react-ui";
import "@joka-7/modeldispatcher-react-ui/styles.css";

// Settings screen — nothing here ever navigates.
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
// field, wherever. This is the one place that opens anything.
function PromptBar({ question }: { question: string }) {
  const [favorite] = useState(loadExternalChatFavorite);
  return (
    <div>
      {/* ...your textarea/send button... */}
      <AskExternallyButton favorite={favorite} question={question} />
    </div>
  );
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
| `config` | `AgentConfig` | yes | The active provider/key/model/Ollama-URL selection. |
| `onConfigChange` | `(config: AgentConfig) => void` | yes | Called with the full updated config on any change. |
| `externalChatFavorite` | `ExternalChatProviderId \| null` | yes | The saved "ask externally" favorite, or `null`. |
| `onExternalChatFavoriteChange` | `(favorite: ExternalChatProviderId \| null) => void` | yes | Called when the user picks or clears a favorite. Persist it yourself — this only reports the choice. |
| `glossaryUrl` | `string` | no | Where "New to AI agents?" links. Defaults to this repo's [`docs/GLOSSARY.md`](../../docs/GLOSSARY.md). |

### `AskExternallyButton` props

| Prop | Type | Required | Purpose |
| --- | --- | --- | --- |
| `favorite` | `ExternalChatProviderId \| null` | yes | The saved favorite. Renders nothing when `null` — there's nothing to ask. |
| `question` | `string` | no | Current prompt, carried into the opened product. |
| `onExternalChat` | `(result: OpenExternalChatResult) => void` | no | Called after a click opens a tab — e.g. to show your own toast. |
| `externalChatDeps` | `OpenExternalChatDeps` | no | Injected `window.open`/clipboard, for tests or a non-browser host. |

## What's in scope, what isn't

This package owns rendering and layout only. It has no opinion on state
management, persistence, or theming beyond the optional default stylesheet
(`md-*` class names, safe to override or ignore entirely). It does not know
about any app's prompts or business logic — same boundary `browser-agent`
already draws. It also enforces one rule at the component boundary:
`ModelPicker` has no way to call `openExternalChat` even internally — that
action only exists in `AskExternallyButton`, so it can't accidentally end up
back on a settings screen.

## Testing

```bash
npm run typecheck
npm test
```

Tests render with `react-dom/client` directly against `jsdom` (no
`@testing-library` dependency) and mock `openExternalChat`'s `window.open`/
clipboard the same way `browser-agent`'s own tests do — no real network, no
real API key needed.
