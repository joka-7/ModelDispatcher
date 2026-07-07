# ModelDispatcher

A reusable internal Python library that acts as a resilient **AI Model
Gateway/Router** shared across applications.

> **Status: architectural skeleton.** This tree defines the public API surface —
> fully typed signatures and complete docstrings — with method bodies left as
> `...` / `raise NotImplementedError`. It imports and passes `mypy --strict`, but
> carries no runtime logic yet. See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the
> full design.

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
