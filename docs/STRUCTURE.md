# Repository structure

Every file in this repo and what is inside it. The tree below is **generated** —
run `python <ogen-ai>/skills/repo_tree/gen_tree.py --project . --output docs/STRUCTURE.md`
to refresh it, and never edit between the markers by hand.

<!-- BEGIN GENERATED TREE (depth=all entries=all) -->
```text
modeldispatcher/
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── release.yml
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
│   │   │   ├── http.test.ts
│   │   │   └── messages.test.ts
│   │   ├── .gitignore
│   │   ├── README.md                     # @joka-7/modeldispatcher-browser-agent
│   │   ├── package-lock.json
│   │   ├── package.json
│   │   ├── tsconfig.build.json
│   │   └── tsconfig.json
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
│   ├── hld/                              # High-Level Design — kept current, narrower and wins over ARCHITECTURE.md…
│   │   └── hld.md                        # ModelDispatcher — High-Level Design (HLD)
│   ├── lld/                              # Low-Level Design — kept current, narrower and wins over ARCHITECTURE.md where…
│   │   └── lld.md                        # ModelDispatcher — Low-Level Design (LLD)
│   ├── .structure-notes.toml
│   ├── STRUCTURE.md                      # Repository structure
│   └── USAGE.md                          # Usage guide
├── examples/
│   └── basic_agent.py                    # Minimal end-to-end usage example
├── src/
│   └── model_dispatcher/
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
│   ├── test_fallback_chain.py            # Behavioral tests for chain-of-responsibility fallback and failover.
│   ├── test_gateway_facade.py            # Behavioral tests for the public facade, perimeter, and API surface.
│   ├── test_onboarding_handoff.py        # Behavioral tests for the two-stage onboarding flow and Stage-2 handoff.
│   ├── test_providers_adapters.py        # Unit tests for the OpenAI/Anthropic/Gemini adapter translation layers.
│   ├── test_quota_manager.py             # Behavioral tests for token-aware quota reservation and reconciliation.
│   ├── test_retry_hints.py               # Unit tests for provider-agnostic "retry after" hint extraction.
│   ├── test_router_triage.py             # Behavioral tests for triage classification and cost-tier routing.
│   └── test_security_redaction.py        # Behavioral tests for credential resolution and secret redaction.
├── .dockerignore
├── .gitignore
├── ARCHITECTURE.md                       # ModelDispatcher — Architecture
├── Dockerfile
├── LICENSE
├── README.md                             # ModelDispatcher
└── pyproject.toml
```
<!-- END GENERATED TREE -->
