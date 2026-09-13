# @joka-7/modeldispatcher-react-ui

One React component for the screen every one of your apps needs and has been
building separately: pick an AI provider and model, enter a key, or skip the
key entirely and hand the question to a free public chat product instead.

Built on top of [`@joka-7/modeldispatcher-browser-agent`](../browser-agent) —
this package is purely the visual layer over that package's provider
registry and `openExternalChat` escape hatch, so the two stay in lockstep.

## Why

StepByLearn, JobFlowTracker, KanDOne, and HighFive each ended up with their
own hand-built "AI settings" screen — same fields, different markup, subtly
different behaviour. `browser-agent` already fixed the *logic* duplication
(one provider registry, one `openExternalChat`). This package fixes the *UI*
duplication: one `<ModelPicker>`, so a new app looks like the others from day
one and a design change ships to every app that imports it.

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
import { loadConfig, saveConfig } from "@joka-7/modeldispatcher-browser-agent";
import { ModelPicker } from "@joka-7/modeldispatcher-react-ui";
import "@joka-7/modeldispatcher-react-ui/styles.css";

function AiSettings() {
  const [config, setConfig] = useState(loadConfig);

  return (
    <ModelPicker
      config={config}
      onConfigChange={(next) => {
        setConfig(next);
        saveConfig(next);
      }}
      question={currentPrompt}
    />
  );
}
```

`ModelPicker` is controlled and stateless about persistence, the same way
`templates/vercel-app`'s `KeyWizard` is: it renders `config`, calls
`onConfigChange` with the full next config on every edit, and never touches
storage itself. Wire it to `loadConfig`/`saveConfig`, your own store, or a
form library — whatever the app already uses.

### Props

| Prop | Type | Required | Purpose |
| --- | --- | --- | --- |
| `config` | `AgentConfig` | yes | The active provider/key/model/Ollama-URL selection. |
| `onConfigChange` | `(config: AgentConfig) => void` | yes | Called with the full updated config on any change. |
| `question` | `string` | no | Current prompt, carried into "try it elsewhere" so the user's question isn't lost when they switch to a free chat product. |
| `onExternalChat` | `(result: OpenExternalChatResult) => void` | no | Called after a "try it elsewhere" click opens a tab — e.g. to show your own toast. |
| `glossaryUrl` | `string` | no | Where "New to AI agents?" links. Defaults to this repo's [`docs/GLOSSARY.md`](../../docs/GLOSSARY.md). |
| `externalChatDeps` | `OpenExternalChatDeps` | no | Injected `window.open`/clipboard, for tests or a non-browser host. |

## What's in scope, what isn't

This package owns rendering and layout only. It has no opinion on state
management, persistence, or theming beyond the optional default stylesheet
(`md-*` class names, safe to override or ignore entirely). It does not know
about any app's prompts or business logic — same boundary `browser-agent`
already draws.

## Testing

```bash
npm run typecheck
npm test
```

Tests render with `react-dom/client` directly against `jsdom` (no
`@testing-library` dependency) and mock `openExternalChat`'s `window.open`/
clipboard the same way `browser-agent`'s own tests do — no real network, no
real API key needed.
