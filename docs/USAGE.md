# Using ModelDispatcher from another app

This is the practical "how do I wire this into *my* app" guide. For internal
design (why the loop/router/fallback chain are built the way they are), see
[`ARCHITECTURE.md`](../ARCHITECTURE.md), [`docs/HLD.md`](HLD.md), and
[`docs/LLD.md`](LLD.md) instead — those are architecture docs, not
usage docs.

There are two distinct consumers: a **Python backend** that runs the gateway
directly in-process, and a **browser/frontend** that talks to that backend
over HTTP through the TypeScript client. Almost every real app needs both.

## 1. Python backend — run the gateway directly

### Install

```bash
pip install "model-dispatcher[openai,anthropic,gemini]"
```

Only install the extras for the vendor SDKs you actually key — each is
optional. Not published yet, or need an unreleased commit? Pin to a git ref
instead: `pip install "model-dispatcher[openai] @ git+https://github.com/joka-7/ModelDispatcher@v0.2.0"`.

### Minimal quickstart

See [`examples/basic_agent.py`](../examples/basic_agent.py) for a full,
runnable version of this (`python examples/basic_agent.py`, no API keys
needed). The shape of it:

```python
from model_dispatcher import (
    CompletionRequest, Message, ModelGateway, ProviderRegistry,
    Role, TenantContext, TenantId, TenantQuota,
)
from model_dispatcher.providers import OpenAIProvider  # or Anthropic/Gemini/Mock

# 1. Register the provider(s) you have keys for.
providers = ProviderRegistry()
providers.register(OpenAIProvider(api_key="sk-..."))
# Groq / OpenRouter / Cerebras / Mistral also register the same way, e.g.:
#   from model_dispatcher.providers import GroqProvider
#   providers.register(GroqProvider(api_key="gsk_..."))
# All four are OpenAIProvider subclasses under the hood (they speak the same
# OpenAI-compatible REST shape at their own base_url), so no extra vendor SDK
# is needed beyond model-dispatcher[openai].

# 2. Build the gateway ONCE at process startup; reuse it for every request.
gateway = ModelGateway.create(providers)

# 3. Describe the caller — quota and credentials are scoped per tenant.
tenant = TenantContext(
    tenant_id=TenantId("user-123"),
    quota=TenantQuota(requests_per_min=20, tokens_per_min=40_000, tokens_per_day=1_000_000),
)

# 4. Dispatch a prompt.
request = CompletionRequest(
    messages=(Message(role=Role.USER, content="Summarise this in one sentence: ..."),),
    tenant=tenant.tenant_id,
)
result = gateway.dispatch(request, tenant)
print(result.final_message.content)
```

### Bring-your-own keys, and pooling more than one

A caller can supply their own key for a provider instead of riding the shared
free tier — set it in `TenantContext.metadata` under `user_key:<family>` (the
part of the provider's `name` before the first `:`, e.g. `"openai"` for a
provider registered as `OpenAIProvider(...)` whose `.name` is
`"openai:gpt-4o-mini"`):

```python
tenant = TenantContext(
    tenant_id=TenantId("user-123"),
    quota=...,
    metadata={"user_key:openai": "sk-...-the-users-own-key"},
)
```

More than one key for the same provider (e.g. several personal keys pooled
for redundancy)? Comma-separate them — the gateway tries each one in order
before falling back to a different provider candidate, so one rate-limited or
revoked key doesn't stall the whole request:

```python
metadata={"user_key:openai": "sk-key-one, sk-key-two, sk-key-three"}
```

To give the agent tools it can call on its own (web search, DB lookups,
internal APIs — anything), register them on a `ToolRegistry` and pass it to
`dispatch(..., tools=registry)`. `examples/basic_agent.py` shows a complete
tool-calling round trip.

### Handling errors the gateway raises

`dispatch`/`adispatch` can raise:

| Exception | Meaning | What to do |
| --- | --- | --- |
| `QuotaExceededError` | The zero-setup free capacity (or the tenant's own quota) is spent. Carries a `.handoff` payload (`{"error": "quota_exceeded", "provider": ..., "action": "trigger_key_wizard"}`). | Return it to your frontend as-is (see §2) so the key wizard can open. |
| `AllProvidersExhausted` | Every routed candidate failed. | Surface a generic 5xx / retry-later to the caller. |
| `PerimeterViolation` / `AuthenticationError` | Request rejected at the edge, or no usable credential. | 400/401 to the caller. |

`demo/backend/app.py` is a complete reference for mapping these onto HTTP
responses (`ModelDispatcherError` carries `http_status`/`error_code` for
exactly this purpose) — copy its `dispatch()` handler as a starting point for
your own FastAPI/Flask/Django endpoint. `templates/vercel-app/api/gateway.py`
is the same pattern behind a Firebase App Check + Auth perimeter, if you're
deploying to Vercel.

## 2. Browser/frontend — talk to your backend via the TS client

The browser never holds provider API keys — it calls **your** backend
endpoint (the one built in §1, wrapped in an HTTP handler), and that endpoint
is what actually imports `model_dispatcher`. `modeldispatcher-client`
is a thin, resilient wrapper around that HTTP call (timeout, retry with
backoff on 5xx, and typed decoding of the `trigger_key_wizard` handoff).

### Install

```bash
npm install modeldispatcher-client
```

(Published to the public npm registry — no `.npmrc` or token needed.)

### Plain usage

```ts
import { GatewayClient } from "modeldispatcher-client";

const client = new GatewayClient({ endpoint: "/api/gateway" });
const outcome = await client.dispatch({ prompt: "..." });

switch (outcome.kind) {
  case "ok":
    console.log(outcome.result.final); // outcome.result: GatewayResult
    break;
  case "handoff":
    // outcome.handoff.provider / .action — open your key-entry UI
    break;
  case "error":
  case "network":
    // show a retry/failure state
    break;
}
```

### React

```tsx
import { useGateway } from "modeldispatcher-client/react";

function Chat({ client }: { client: GatewayClient }) {
  const { dispatch, wizard, dismissWizard } = useGateway(client);
  // dispatch(...) returns the same typed outcome as above;
  // `wizard` is automatically populated when a trigger_key_wizard handoff
  // comes back, so you can render your key-entry modal declaratively.
}
```

`templates/vercel-app/app/components/KeyWizard.tsx` and
`demo/frontend/src/App.tsx` are working examples of that modal.

## 3. Full-stack starting point

Don't want to wire §1 and §2 together by hand? Copy
[`templates/vercel-app/`](../templates/vercel-app) — a complete Next.js +
Vercel Python Function reference wiring both sides behind Firebase App Check
+ Auth, with per-tenant quota isolation from a verified Firebase Auth `uid`.
See that folder's own README for setup.

## 4. No-backend browser apps — `browser-agent` + `react-ui` (BYOK)

If an app has no backend at all — a static site, or a frontend that simply
doesn't want to run the Python gateway — skip §1/§2 entirely and call
providers straight from the browser with the caller's own key:

```bash
npm install modeldispatcher-browser-agent modeldispatcher-react-ui
```

```tsx
import { useState } from "react";
import { loadConfig, saveConfig, complete } from "modeldispatcher-browser-agent";
import { ModelPicker } from "modeldispatcher-react-ui";
import "modeldispatcher-react-ui/styles.css";

function AiSettings() {
  const [config, setConfig] = useState(loadConfig);
  return (
    <ModelPicker
      config={config}
      onConfigChange={(next) => { setConfig(next); saveConfig(next); }}
      /* ...externalChatFavorite props, see clients/react-ui/README.md... */
    />
  );
}

async function ask(question: string) {
  return complete(loadConfig(), question); // tries every configured provider/key in order
}
```

`ModelPicker` is the settings screen (add providers, models, pooled keys —
never navigates); `AskExternallyButton` is the separate "ask a favorite free
app instead" action. Full props and the settings/action split rationale:
[`clients/react-ui/README.md`](../clients/react-ui/README.md).

### Making the dispatcher optional per app

Rolling this into an app that already has its own AI settings screen and its
own calling code doesn't have to be all-or-nothing. `resolveDispatcherFeatures`
is the framework's own answer to "on or off, and who decides" — a developer/
deploy-time config, never a switch an end user sees:

```ts
// modeldispatcher.config.ts — your app's own config module, not exported to users
import { resolveDispatcherFeatures } from "modeldispatcher-browser-agent";

export const dispatcherFeatures = resolveDispatcherFeatures({
  // Render <ModelPicker>/<AskExternallyButton> vs. this app's existing settings UI.
  ui: import.meta.env.VITE_MODEL_DISPATCHER_UI !== "false",
  // Route AI calls through complete()/streamComplete() (with its
  // multi-provider/multi-key fallback) vs. this app's existing call path.
  dispatch: import.meta.env.VITE_MODEL_DISPATCHER_DISPATCH !== "false",
});
```

```tsx
function AiSettingsScreen() {
  return dispatcherFeatures.ui ? <ModelPicker {...props} /> : <LegacyAiSettings />;
}

async function askAi(question: string) {
  return dispatcherFeatures.dispatch ? complete(loadConfig(), question) : legacyAskAi(question);
}
```

Two independent flags, not one, because they answer different questions: `ui`
controls what the settings screen renders, `dispatch` controls what actually
makes the network call — an app can adopt the shared UI while still routing
through its own backend, or vice versa, while it migrates. Both default to
`true` (calling `resolveDispatcherFeatures()` with no overrides turns
everything on), so an app opts *out* per feature rather than opting in from a
cold start. `resolveDispatcherFeatures` never reads environment variables
itself — every bundler exposes them differently
(`import.meta.env.VITE_*`, `process.env.NEXT_PUBLIC_*`,
`process.env.REACT_APP_*`, …) — so each app's own config module resolves its
own env var and passes the boolean in; the flag names and shapes are what's
worth keeping consistent across apps, not the env var mechanism itself.

## 5. Versioning across multiple consuming apps

Once you've got more than one app depending on ModelDispatcher, pin every
consumer to the same tagged version and bump them together when you cut a
release (`git tag vX.Y.Z && git push --tags` triggers
`.github/workflows/release.yml`, which publishes both the PyPI package and
the npm client from that tag). See the root [`README.md`](../README.md)
install section for the exact pinning syntax.
