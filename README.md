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

The TypeScript client (`@joka-7/modeldispatcher-client`) is published to
GitHub Packages — see [`clients/typescript`](./clients/typescript). It talks to
*your own backend*, which is what runs the Python gateway above.

For an app with **no backend at all** — a pure browser app doing
bring-your-own-key calls straight to a provider — see
[`clients/browser-agent`](./clients/browser-agent)
(`@joka-7/modeldispatcher-browser-agent`) instead: the same multi-provider
idea (Gemini/OpenAI/Anthropic/Groq/Ollama), running client-side with no
server and no vendor SDK required.

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
blueprints, and algorithmic flows, and [`docs/hld/hld.md`](docs/hld/hld.md) /
[`docs/lld/lld.md`](docs/lld/lld.md) for the design docs that stay current
when behavior evolves past what's written there.

<!-- BEGIN GENERATED TREE (depth=1 entries=all) -->
```text
ModelDispatcher/
├── .github/
├── clients/         # Non-Python integration layers, documented in ARCHITECTURE.md's…
├── demo/            # Interactive end-to-end demo of the gateway
├── docs/
├── examples/
├── src/
├── templates/
├── tests/           # Behavioral test suite (routing, fallback, quota, agent loop, security,…
├── .ai              # Ogen-ai submodule — the shared source of rules, skills and the ai-sync…
├── .dockerignore
├── .gitignore
├── .gitleaksignore
├── .gitmodules
├── AGENTS.md        # The compiled coding rules every AI assistant reads — generated, do not…
├── ARCHITECTURE.md  # ModelDispatcher — Architecture
├── CLAUDE.md        # Claude Code's copy of AGENTS.md (generated)
├── Dockerfile
├── GEMINI.md        # Gemini CLI's copy of AGENTS.md (generated)
├── LICENSE
├── README.md        # ModelDispatcher
├── ai-config.toml   # Which rule fragments and target tools ai-sync compiles for this repo
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
