# ModelDispatcher

A reusable internal Python library that acts as a resilient **AI Model
Gateway/Router** shared across applications.

> **Status: working library + demo.** The core runs end-to-end (routing,
> fallback, quota, agent loop, onboarding), ships real OpenAI/Anthropic adapters,
> is covered by a behavioral test suite, and has an interactive FastAPI + React
> demo. See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the design and
> [`demo/`](./demo) to run it in a browser.

## What it does

- **Strategy providers** — every model backend implements one `ModelProvider`
  interface, so providers are hot-swappable.
- **Chain-of-Responsibility fallback** — rate limits and exhaustion are intercepted
  and the request transparently escalates to the next candidate model.
- **Native agent orchestration** — a small, dependency-free tool-calling loop with
  explicit state management (no heavy agent framework).
- **Triage & cost routing** — cheap/free models for simple work, premium models
  reserved for complex reasoning.
- **Token-aware multi-tenant quotas** — pre-flight reservation + post-call
  reconciliation per tenant.
- **Secure proxy perimeter** — inbound validation and a credential-precedence chain.
- **Two-stage onboarding** — zero-setup free tier by default; when limits are hit,
  a structured `402`/`429` handoff payload drives a GUI key wizard.

## Install

```bash
pip install "model-dispatcher[openai,anthropic,gemini]"
```

Each provider adapter is an optional extra — install only the ones you key.
Not yet published to PyPI (or need a version ahead of the latest tag)? Pin to
a git ref instead:

```bash
pip install "model-dispatcher[openai] @ git+https://github.com/joka-7/ModelDispatcher@v0.2.0"
```

The TypeScript client (`modeldispatcher-client`) is published to
the public npm registry — see [`clients/typescript`](./clients/typescript). It talks to
*your own backend*, which is what runs the Python gateway above.

For an app with **no backend at all** — a pure browser app doing
bring-your-own-key calls straight to a provider — see
[`clients/browser-agent`](./clients/browser-agent)
(`modeldispatcher-browser-agent`) instead: the same multi-provider,
multi-key fallback idea (Gemini/OpenAI/Anthropic/Groq/Ollama, several pooled
keys per vendor), running client-side with no server and no vendor SDK
required.

Building the settings screen for that in React? See
[`clients/react-ui`](./clients/react-ui)
(`modeldispatcher-react-ui`) for `<ModelPicker>` — add one or more
providers, a model picked from a curated list per provider, pooled API keys,
saving a favorite free AI app, and a link to the interactive
[`docs/ai-glossary.html`](./docs/ai-glossary.html) for first-time users, with
nothing in it that navigates — plus `<AskExternallyButton>`, the separate
action that actually opens that favorite from wherever the user is asking a
question, and `<PasteExternalReply>` for apps that need the answer back in
a specific structure (parsing it is the app's own job — this just captures
the raw pasted text). So every app renders the same picker instead of each
one hand-building its own, and a settings screen never redirects on its own.

Adopting either isn't all-or-nothing: `resolveDispatcherFeatures` from
`browser-agent` gives each app's own developer — never the end user — two
flags (`ui`, `dispatch`) to opt out per app during rollout instead of
switching everything on at once. See
[`docs/USAGE.md`](./docs/USAGE.md#4-no-backend-browser-apps--browser-agent--react-ui-byok).

## Quickstart

No API keys needed — this uses the keyless `MockProvider`:

```bash
pip install -e .            # from a clone of this repo
python examples/basic_agent.py
```

```python
from model_dispatcher import (
    CompletionRequest, Message, ModelGateway, ProviderRegistry,
    Role, TenantContext, TenantId, TenantQuota,
)
from model_dispatcher.providers import MockProvider  # swap for OpenAIProvider, etc.

providers = ProviderRegistry()
providers.register(MockProvider("mock:free"))
gateway = ModelGateway.create(providers)  # build once at startup

tenant = TenantContext(
    tenant_id=TenantId("demo-user"),
    quota=TenantQuota(requests_per_min=20, tokens_per_min=40_000, tokens_per_day=1_000_000),
)
request = CompletionRequest(
    messages=(Message(role=Role.USER, content="Hello!"),),
    tenant=tenant.tenant_id,
)
result = gateway.dispatch(request, tenant)
print(result.final_message.content)
```

See [`examples/basic_agent.py`](./examples/basic_agent.py) for the full
version with a tool the agent calls on its own.

## Using it from another app

**[`docs/USAGE.md`](./docs/USAGE.md)** is the integration guide: installing
into a Python backend, wiring the TypeScript client to a frontend, mapping
gateway errors onto HTTP responses, and pinning versions across multiple
consuming repos.

## Layout

See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the directory layout, class
blueprints, and algorithmic flows, and [`docs/HLD.md`](docs/HLD.md) /
[`docs/LLD.md`](docs/LLD.md) for the design docs that stay current
when behavior evolves past what's written there.

<!-- BEGIN GENERATED TREE (depth=all entries=all) -->
```text
ModelDispatcher/
├── .github/
│   ├── workflows/
│   │   ├── ci.yml
│   │   ├── release.yml
│   │   └── security.yml
│   ├── copilot-instructions.md           # Copilot's copy of AGENTS.md (generated)
│   └── dependabot.yml
├── clients/                              # Non-Python integration layers, documented in ARCHITECTURE.md's…
│   ├── browser-agent/                    # Browser-native TypeScript client (no server) — see its own README.md
│   │   ├── src/
│   │   │   ├── providers/
│   │   │   │   ├── anthropic.ts
│   │   │   │   ├── gemini.ts
│   │   │   │   ├── ollama.ts
│   │   │   │   └── openaiCompatible.ts
│   │   │   ├── agent.ts
│   │   │   ├── config.ts
│   │   │   ├── externalChat.ts
│   │   │   ├── externalChatFavorite.ts
│   │   │   ├── features.ts
│   │   │   ├── http.ts
│   │   │   ├── index.ts
│   │   │   ├── messages.ts
│   │   │   ├── registry.ts
│   │   │   └── types.ts
│   │   ├── tests/
│   │   │   ├── providers/
│   │   │   │   ├── anthropic.test.ts
│   │   │   │   ├── gemini.test.ts
│   │   │   │   ├── ollama.test.ts
│   │   │   │   └── openaiCompatible.test.ts
│   │   │   ├── agent.test.ts
│   │   │   ├── config.test.ts
│   │   │   ├── externalChat.test.ts
│   │   │   ├── externalChatFavorite.test.ts
│   │   │   ├── features.test.ts
│   │   │   ├── http.test.ts
│   │   │   └── messages.test.ts
│   │   ├── .gitignore
│   │   ├── README.md                     # Modeldispatcher-browser-agent
│   │   ├── package-lock.json
│   │   ├── package.json
│   │   ├── tsconfig.build.json
│   │   └── tsconfig.json
│   ├── react-ui/                         # Shared React model/agent picker component — see its own README.md
│   │   ├── screenshots/
│   │   │   ├── action.png
│   │   │   └── settings.png
│   │   ├── src/
│   │   │   ├── AskExternallyButton.tsx
│   │   │   ├── ConversationIntro.tsx
│   │   │   ├── ModelPicker.tsx
│   │   │   ├── NoProviderPrompt.tsx
│   │   │   ├── PasteExternalReply.tsx
│   │   │   ├── i18n.ts
│   │   │   ├── index.ts
│   │   │   └── styles.css
│   │   ├── tests/
│   │   │   ├── AskExternallyButton.test.tsx
│   │   │   ├── ConversationIntro.test.tsx
│   │   │   ├── ModelPicker.test.tsx
│   │   │   ├── NoProviderPrompt.test.tsx
│   │   │   ├── PasteExternalReply.test.tsx
│   │   │   └── setup.ts
│   │   ├── .gitignore
│   │   ├── README.md                     # Modeldispatcher-react-ui
│   │   ├── package-lock.json
│   │   ├── package.json
│   │   ├── tsconfig.build.json
│   │   ├── tsconfig.json
│   │   └── vitest.config.ts
│   └── typescript/                       # Node/server TypeScript client — see its own README.md
│       ├── src/
│       │   ├── interceptors/
│       │   │   ├── appcheck.ts
│       │   │   ├── auth.ts
│       │   │   ├── handoff.ts
│       │   │   ├── interceptor.ts
│       │   │   ├── retry.ts
│       │   │   └── timeout.ts
│       │   ├── react/
│       │   │   └── useGateway.ts
│       │   ├── client.ts
│       │   ├── events.ts
│       │   ├── index.ts
│       │   └── types.ts
│       ├── tests/
│       │   ├── client.test.ts
│       │   └── units.test.ts
│       ├── .gitignore
│       ├── package-lock.json
│       ├── package.json
│       ├── tsconfig.build.json
│       └── tsconfig.json
├── demo/                                 # Interactive end-to-end demo of the gateway
│   ├── backend/                          # FastAPI app wrapping ModelGateway
│   │   ├── app.py                        # FastAPI demo backend exposing the ModelDispatcher gateway.
│   │   └── requirements.txt
│   ├── frontend/                         # Vite/React UI driving the demo backend
│   │   ├── src/
│   │   │   ├── App.tsx
│   │   │   ├── api.ts
│   │   │   ├── main.tsx
│   │   │   └── styles.css
│   │   ├── .gitignore
│   │   ├── index.html
│   │   ├── package-lock.json
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   └── vite.config.ts
│   └── README.md                         # ModelDispatcher Demo (FastAPI + React)
├── docs/
│   ├── .structure-notes.toml
│   ├── GLOSSARY.md                       # Plain-language AI/agent/prompt/key glossary linked from ModelPicker
│   ├── HLD.md                            # High-Level Design — kept current, narrower and wins over ARCHITECTURE.md…
│   ├── LLD.md                            # Low-Level Design — kept current, narrower and wins over ARCHITECTURE.md where…
│   ├── STRUCTURE.md                      # Repository structure
│   ├── USAGE.md                          # Usage guide
│   └── ai-glossary.html                  # Interactive EN/FR/HE glossary site — ModelPicker's default glossaryUrl
├── examples/
│   └── basic_agent.py                    # Minimal end-to-end usage example
├── src/
│   └── model_dispatcher/
│       ├── byok/                         # SERVER + BYOK — registry builder, timeout-bounded dispatch
│       │   ├── __init__.py               # Server-hosted BYOK integration: pooled server keys plus visitor keys.
│       │   ├── dispatch.py               # Timeout-bounded dispatch for a server serving live visitor requests.
│       │   └── registry.py               # Registry building for a server pooling its own keys with visitor BYOK keys.
│       ├── fallback/                     # CHAIN OF RESPONSIBILITY — handlers + chain executor + conditions
│       │   ├── __init__.py               # Chain-of-Responsibility fallback handling.
│       │   ├── chain.py                  # Builder and executor for the fallback chain of responsibility.
│       │   ├── conditions.py             # Centralised failure-classification predicates for the fallback chain.
│       │   └── handlers.py               # Chain-of-Responsibility handlers for a single model invocation.
│       ├── observability/                # Redaction-aware logging + vendor-neutral metrics
│       │   ├── __init__.py               # Observability: redaction-aware logging and vendor-neutral metrics.
│       │   ├── logging.py                # Structured, redaction-aware logging.
│       │   └── metrics.py                # Vendor-neutral metrics hooks.
│       ├── onboarding/                   # TWO-STAGE — resolver + KeyWizardHandoff payload
│       │   ├── __init__.py               # Two-stage onboarding: zero-setup default and guided GUI handoff.
│       │   ├── flow.py                   # Two-stage onboarding resolution.
│       │   └── handoff.py                # The Stage-2 GUI handoff contract.
│       ├── orchestration/                # NATIVE LOOP — AgentLoop, ConversationState, tools, results
│       │   ├── __init__.py               # Native agent orchestration: the tool-calling execution loop.
│       │   ├── loop.py                   # The native agent execution loop.
│       │   ├── result.py                 # Result objects returned by the agent loop.
│       │   ├── state.py                  # Mutable conversation state for one agent run.
│       │   └── tools.py                  # Tool registration and execution for the agent loop.
│       ├── providers/                    # STRATEGY — ModelProvider + registry + concrete adapters
│       │   ├── __init__.py               # Provider strategies and their registry (Strategy Pattern).
│       │   ├── anthropic_provider.py     # Anthropic provider strategy.
│       │   ├── base.py                   # The Strategy interface for model providers.
│       │   ├── gemini_provider.py        # Google Gemini provider strategy.
│       │   ├── mock_provider.py          # In-memory mock provider for tests and the zero-dependency demo.
│       │   ├── openai_compatible.py      # Adapters for vendors that speak the OpenAI chat-completions REST shape.
│       │   ├── openai_provider.py        # OpenAI provider strategy.
│       │   ├── registry.py               # Registry and lookup for provider strategies.
│       │   └── retry_hints.py            # Extracting a vendor-supplied "retry after" hint from a rate-limit failure.
│       ├── quota/                        # TOKEN QUOTAS — manager, tenant, tokenizer, store (in-memory)
│       │   ├── __init__.py               # Token-aware, multi-tenant quota management.
│       │   ├── manager.py                # Token-aware, multi-tenant quota manager.
│       │   ├── store.py                  # Persistence seam for tenant quota counters.
│       │   ├── tenant.py                 # Per-tenant quota definitions and runtime context.
│       │   └── tokenizer.py              # Pre-flight token estimation.
│       ├── routing/                      # TRIAGE — TaskTriage (complexity) + ModelRouter (candidate order)
│       │   ├── __init__.py               # Triage and cost-aware routing.
│       │   ├── router.py                 # Cost-aware model router.
│       │   └── triage.py                 # Task triage: classify how much reasoning a request demands.
│       ├── security/                     # PERIMETER — validator, credential resolver, redaction
│       │   ├── __init__.py               # Secure proxy perimeter: validation, credentials, and redaction.
│       │   ├── credentials.py            # Credential resolution with a strict precedence chain.
│       │   ├── perimeter.py              # Secure proxy perimeter validation.
│       │   └── redaction.py              # Secret and PII redaction for logs and metrics.
│       ├── __init__.py                   # A resilient AI Model Gateway/Router.
│       ├── _async_bridge.py              # Internal helpers for offering sync and async APIs from one core.
│       ├── config.py                     # Declarative configuration for a :class:`ModelGateway` instance.
│       ├── exceptions.py                 # HTTP-aware exception hierarchy for the gateway.
│       ├── gateway.py                    # The public facade: :class:`ModelGateway`.
│       ├── py.typed                      # PEP 561 marker — this package ships inline type hints
│       └── types.py                      # Shared vocabulary for the gateway.
├── templates/
│   └── vercel-app/                       # Starter template: a Vercel app pre-wired to ModelGateway
│       ├── api/
│       │   ├── _lib/
│       │   │   ├── __init__.py           # Internal helpers for the Vercel gateway wrapper.
│       │   │   ├── appcheck.py           # Firebase App Check verification for the Vercel perimeter (Strategy pattern).
│       │   │   ├── auth.py               # Firebase Auth-backed tenant identity for the Vercel perimeter (Strategy…
│       │   │   ├── firebase_app.py       # Shared Firebase Admin SDK bootstrap.
│       │   │   ├── http.py               # Pure request/response (de)serialization helpers for the gateway wrapper.
│       │   │   ├── pipeline.py           # The transport-agnostic dispatch pipeline.
│       │   │   └── wiring.py             # Gateway assembly for the Vercel function.
│       │   ├── tests/
│       │   │   ├── conftest.py           # Put the `api/` directory on `sys.path` so `_lib` imports resolve.
│       │   │   ├── test_auth.py          # Tests for the Firebase Auth ID-token verifier's testable-without-firebase…
│       │   │   ├── test_firebase_app.py  # Tests for the shared Firebase bootstrap's credential-parsing helper.
│       │   │   ├── test_pipeline.py      # Behavioural tests for the gateway wrapper's dispatch pipeline.
│       │   │   └── test_wiring.py        # Tests for per-tier live-vs-mock provider selection in `_lib.wiring`.
│       │   ├── gateway.py                # Vercel serverless entrypoint: the thin gateway wrapper (Adapter pattern).
│       │   └── requirements.txt
│       ├── app/
│       │   ├── components/
│       │   │   └── KeyWizard.tsx
│       │   ├── lib/
│       │   │   └── gateway.ts
│       │   ├── globals.css
│       │   ├── layout.tsx
│       │   └── page.tsx
│       ├── .env.example
│       ├── .gitignore
│       ├── FIREBASE_APPCHECK_SETUP.md    # Firebase App Check setup for the template
│       ├── README.md                     # ModelDispatcher — Vercel integration template
│       ├── package.json
│       ├── tsconfig.json
│       └── vercel.json
├── tests/                                # Behavioral test suite (routing, fallback, quota, agent loop, security,…
│   ├── conftest.py                       # Shared fixtures for the behavioral test-suite.
│   ├── test_agent_loop.py                # Behavioral tests for the native agent tool-calling loop.
│   ├── test_byok.py                      # Behavioral tests for the `byok` server-integration subpackage.
│   ├── test_fallback_chain.py            # Behavioral tests for chain-of-responsibility fallback and failover.
│   ├── test_gateway_facade.py            # Behavioral tests for the public facade, perimeter, and API surface.
│   ├── test_onboarding_handoff.py        # Behavioral tests for the two-stage onboarding flow and Stage-2 handoff.
│   ├── test_providers_adapters.py        # Unit tests for the OpenAI/Anthropic/Gemini adapter translation layers.
│   ├── test_quota_manager.py             # Behavioral tests for token-aware quota reservation and reconciliation.
│   ├── test_retry_hints.py               # Unit tests for provider-agnostic "retry after" hint extraction.
│   ├── test_router_triage.py             # Behavioral tests for triage classification and cost-tier routing.
│   └── test_security_redaction.py        # Behavioral tests for credential resolution and secret redaction.
├── .ai                                   # Ogen-ai submodule — the shared source of rules, skills and the ai-sync…
├── .dockerignore
├── .gitignore
├── .gitleaksignore
├── .gitmodules
├── AGENTS.md                             # The compiled coding rules every AI assistant reads — generated, do not…
├── ARCHITECTURE.md                       # ModelDispatcher — Architecture
├── CLAUDE.md                             # Claude Code's copy of AGENTS.md (generated)
├── Dockerfile
├── GEMINI.md                             # Gemini CLI's copy of AGENTS.md (generated)
├── LICENSE
├── README.md                             # ModelDispatcher
├── SECURITY.md                           # Security Policy
├── ai-config.local.md                    # Project-specific rules appended verbatim to the generated AGENTS.md
├── ai-config.toml                        # Which rule fragments and target tools ai-sync compiles for this repo
└── pyproject.toml
```
<!-- END GENERATED TREE -->

Full annotated tree, every file: [`docs/STRUCTURE.md`](docs/STRUCTURE.md). Generated —
regenerate after adding/renaming a file with:
```bash
python .ai/skills/repo_tree/gen_tree.py --project . --output docs/STRUCTURE.md
python .ai/skills/repo_tree/gen_tree.py --project . --output README.md --max-depth 1
```

## Development

```bash
pip install -e ".[dev]"
ruff check src tests
mypy --strict src
pytest
```

Requires Python >= 3.11.

## Try it in a browser

```bash
docker build -t model-dispatcher-demo .
docker run --rm -p 8000:8000 model-dispatcher-demo   # http://localhost:8000
```

The demo drives the real gateway through keyless mock providers, so you can watch
routing, fallback, quota meters, and the key-wizard handoff without any API keys.
See [`demo/README.md`](./demo/README.md) for the two-process dev setup.
