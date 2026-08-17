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
GitHub Packages — see [`clients/typescript`](./clients/typescript).

## Layout

See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the directory layout, class
blueprints, and algorithmic flows.

## Development

```bash
pip install -e ".[dev]"
ruff check src tests
mypy --strict src
pytest
```

Requires Python >= 3.12.

## Try it in a browser

```bash
docker build -t model-dispatcher-demo .
docker run --rm -p 8000:8000 model-dispatcher-demo   # http://localhost:8000
```

The demo drives the real gateway through keyless mock providers, so you can watch
routing, fallback, quota meters, and the key-wizard handoff without any API keys.
See [`demo/README.md`](./demo/README.md) for the two-process dev setup.
