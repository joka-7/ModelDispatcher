# ModelDispatcher — Architecture

`ModelDispatcher` is a reusable internal library that acts as a central **AI Model
Gateway/Router**. A consuming application constructs one `ModelGateway` at
startup and dispatches every LLM/agent request through it. The gateway picks a
cost-appropriate model, transparently fails over on rate limits, runs a native
tool-calling loop, enforces per-tenant token quotas, validates a security
perimeter, and drives a two-stage onboarding flow.

> **Status:** architectural skeleton. Signatures, types, and docstrings are
> complete and pass `mypy --strict`; method bodies raise `NotImplementedError`.

## Design pillars

| Concern | Pattern | Where |
| --- | --- | --- |
| Pluggable model backends | **Strategy** | `providers/` (`ModelProvider`) |
| Rate-limit / exhaustion failover | **Chain of Responsibility** | `fallback/` |
| Agent tool-calling & state | **Native execution loop** | `orchestration/` |
| Cost control | **Triage → tiered routing** | `routing/` |
| Multi-tenant fairness | **Reserve/commit token quotas** | `quota/` |
| Untrusted-edge safety | **Perimeter + credential precedence** | `security/` |
| Onboarding | **Two-stage: zero-setup → GUI handoff** | `onboarding/` |
| One entry point | **Facade** | `gateway.py` (`ModelGateway`) |

## Directory layout

```
src/model_dispatcher/
├── gateway.py          # Facade: ModelGateway.dispatch / adispatch
├── config.py           # GatewaySettings, RoutingPolicy, SecuritySettings, QuotaDefaults
├── types.py            # Message, Usage, enums, request/response DTOs, JSON/TenantId aliases
├── exceptions.py       # HTTP-aware error hierarchy (http_status + to_payload)
├── _async_bridge.py    # internal: drive the async core from sync entry points
├── providers/          # STRATEGY — ModelProvider + registry + concrete adapters
├── routing/            # TRIAGE — TaskTriage (complexity) + ModelRouter (candidate order)
├── fallback/           # CHAIN OF RESPONSIBILITY — handlers + chain executor + conditions
├── orchestration/      # NATIVE LOOP — AgentLoop, ConversationState, tools, results
├── quota/              # TOKEN QUOTAS — manager, tenant, tokenizer, store (in-memory)
├── security/           # PERIMETER — validator, credential resolver, redaction
├── onboarding/         # TWO-STAGE — resolver + KeyWizardHandoff payload
└── observability/      # redaction-aware logging + vendor-neutral metrics
```

## Concurrency model

Both sync and async APIs are first-class. The async path (`adispatch`,
`acomplete`, `ahandle`, `arun`, `aexecute`) is the native core; the sync methods
delegate through `_async_bridge.run_sync`, which uses `asyncio.run` when no loop
is active and a worker-thread loop when one already is.

## Component blueprints

### Providers — Strategy (`providers/`)

`ModelProvider` (ABC) is the single interface every backend implements:
`complete`/`acomplete`, `estimate_tokens`, and `classify_error`. The last one is
the key seam — each adapter maps its vendor SDK's exceptions onto the normalised
`ErrorClass` enum (`RATE_LIMIT | QUOTA | AUTH | TRANSIENT | INVALID | CONTENT`),
so nothing downstream ever imports a vendor exception type. Adapters
(`OpenAIProvider`, `AnthropicProvider`, `GeminiProvider`, `LocalProvider`) import
their SDKs lazily inside method bodies, keeping the core dependency-free.
`GroqProvider`, `OpenRouterProvider`, `CerebrasProvider`, and `MistralProvider`
(`providers/openai_compatible.py`) are thin `OpenAIProvider` subclasses that
just fix the base URL, default model, and identity — all four vendors speak
the same OpenAI chat-completions REST shape, so there's no separate
translation layer to maintain for them.
`ProviderRegistry` indexes providers by name and tier and answers the router's
cheapest-capable queries.

### Routing — Triage & cost control (`routing/`)

`TaskTriage.classify` assigns a `TaskComplexity` from cheap, deterministic
signals (input size, tool surface, reasoning markers, requested output size).
`ModelRouter.route` maps that verdict onto a minimum `ModelTier` via
`RoutingPolicy`, filters by required `ProviderCapability`, and returns an
**ordered, cheapest-first candidate list**. That list is literally the seed the
fallback chain consumes — routing and fallback ordering are one decision.

### Fallback — Chain of Responsibility (`fallback/`)

An `InvocationContext` (request + mutable `candidates` list + attempt log)
travels through linked `FallbackHandler`s, each returning a `HandlerOutcome`:

1. `PerimeterHandler` — security edge check.
2. `CredentialHandler` — resolve key via the precedence chain.
3. `QuotaHandler` — pre-flight `reserve()`; hard breach → `QuotaExceededError`.
4. `ModelInvocationHandler` — call the current candidate.
5. `RateLimitHandler` — turn a provider 429/exhaustion into `FALLBACK`.
6. `RetryHandler` — bounded backoff for `TRANSIENT`.

`FallbackChain.execute` interprets outcomes: `CONTINUE` advances, `SUCCESS`
returns, `FALLBACK` pops the current candidate and restarts from the head, `STOP`
raises. When candidates are spent it raises `AllProvidersExhausted` (503).
`conditions.py` centralises `is_retryable` / `is_fallback_worthy` / `is_terminal`
so every handler agrees on failure semantics.

### Orchestration — Native agent loop (`orchestration/`)

`AgentLoop.run`/`arun` is the deliberate replacement for a heavy agent framework:
a small explicit loop over `ConversationState`. Each turn snapshots state into a
`CompletionRequest`, dispatches it **through the fallback chain**, appends the
assistant message and usage, and — if the model requested tools — runs them via
`ToolExecutor` and iterates; otherwise it returns a `RunResult`. Because every
turn (including tool follow-ups) goes through the same chain, fallback, quota, and
security apply uniformly. Guards: `max_iterations` and an optional `deadline`.

### Quota — Token-aware, multi-tenant (`quota/`)

Two-phase enforcement around each call:

- `QuotaManager.reserve(tenant, estimate, provider)` → `QuotaDecision`
  (`ALLOW | SOFT_LIMIT | DENY`) checked against the tenant's windows
  (per-minute, per-day, optional budget). `TokenCounter.estimate` supplies a
  conservative pre-flight estimate.
- `QuotaManager.commit(tenant, actual_usage)` reconciles the estimate against the
  provider-reported usage so counters do not drift.

Counters live behind the `QuotaStore` **Protocol**. This build ships only
`InMemoryQuotaStore` (single-process, dict-backed); a distributed backend can be
dropped in later without touching callers.

### Security — Perimeter (`security/`)

`PerimeterValidator.validate` is the single choke point for untrusted inbound
requests: tenant authN, payload-size caps, egress provider allowlist, and
structural/injection sanity checks — failing fast with `PerimeterViolation`
(403). `CredentialResolver.resolve_candidates` implements the precedence chain
**user key(s) → tenant key(s) → global app key → free tier**, which is the
mechanical basis of onboarding Stage 1. A tenant may pool more than one key per
provider (comma-separated in `TenantContext.metadata`); `ModelInvocationHandler`
rotates through all of them — retrying transient failures, moving to the next
key on rate-limit/quota/auth, and only falling back to the *next provider
candidate* once every pooled key is exhausted. `SecretRedactor` scrubs
secrets/PII from anything bound for logs or metrics; the raw key itself never
appears in a `Credential`'s `repr()`, only its masked `secret_ref`.

### Onboarding — Two-stage flow (`onboarding/`)

- **Stage 1 (zero-setup):** a brand-new tenant has no key, so `CredentialResolver`
  silently uses the rate-limited global app key / free tier. `OnboardingResolver`
  reports `ZERO_SETUP`.
- **Stage 2 (guided handoff):** once that shared capacity is spent,
  `KeyWizardHandoff.build` produces a `HandoffResponse`, wrapped in
  `QuotaExceededError`. Its `to_payload()` is the exact front-end contract:

  ```json
  {"error": "quota_exceeded", "provider": "openai", "action": "trigger_key_wizard"}
  ```

  with `http_status` `402` (budget/upgrade wall) or `429` (rolling rate window).
  The library returns the structured object; the web app maps it to HTTP and
  launches its key wizard.

### Exceptions (`exceptions.py`)

Every error subclasses `ModelDispatcherError` and carries `http_status` +
`to_payload()`, so a web layer maps any failure to a response in one `except`.

```
ModelDispatcherError            (500)
├── PerimeterViolation          (403)
├── AuthenticationError         (401)
├── RateLimitError              (429)   # internal fallback signal
├── QuotaExceededError          (402/429, carries the key-wizard handoff)
├── AllProvidersExhausted       (503)
└── ToolExecutionError          (500)
```

## End-to-end dispatch flow

```
dispatch(request, tenant):
  1. PerimeterValidator.validate(request, tenant)      # 403 on edge failure
  2. complexity = TaskTriage.classify(request)         # TRIVIAL..COMPLEX
  3. candidates = ModelRouter.route(request, complexity)   # cheap → premium
  4. chain = FallbackChain.build([Perimeter, Credential, Quota,
                                  ModelInvocation, RateLimit, Retry])
  5. result = AgentLoop.run(state, tools, chain, candidates, deadline=…)
       └─ per turn: chain.execute → (tool calls? execute + loop : return)
  6. QuotaManager.commit(tenant, result.usage)         # reconcile estimate vs real
  7. return result
     # QuotaExceededError bubbles up carrying the Stage-2 trigger_key_wizard payload
```

### Quota + onboarding decision (inside the chain)

```
QuotaHandler:
  est = TokenCounter.estimate(request)
  decision = QuotaManager.reserve(tenant, est, provider)
  ALLOW       -> CONTINUE
  SOFT_LIMIT  -> CONTINUE (+ warn metric)
  DENY:
     if OnboardingResolver.stage(tenant) == ZERO_SETUP and a cheaper free candidate remains:
        return FALLBACK                # stay zero-setup, try the cheaper model
     else:
        handoff = OnboardingResolver.escalate(tenant, provider, rate_window=…)
        raise QuotaExceededError(handoff)   # Stage-2 GUI handoff
```

## Extension points

- **New provider:** implement `ModelProvider` and register it — no other change.
- **Custom triage:** pass a `ComplexityScorer` callable to `TaskTriage`.
- **Distributed quotas:** implement the `QuotaStore` Protocol.
- **New fallback behaviour:** add a `FallbackHandler` and place it in the chain.
- **Metrics backend:** implement the `MetricsSink` Protocol.

## Quality bar

PEP 8 via `ruff` (incl. docstring checks), advanced typing verified by
`mypy --strict`, complete docstrings with explicit *Algorithm* sections on
non-trivial methods, and structural contract tests under `tests/`.
```bash
pip install -e ".[dev]"
ruff check src tests && ruff format --check src tests
mypy --strict src
pytest
```

## Lowering the Python floor (3.12 → 3.11)

`requires-python` was originally `>=3.12`, driving the codebase to lean on
3.12-only syntax in a few spots: PEP 695 `type` alias statements and generic
function syntax (`def f[T](...)`), plus `typing.override` (stdlib since 3.12,
PEP 698). None of that was load-bearing — it was just the newest available
syntax at the time — so when a consuming app (LangShift, `>=3.10`) needed a
lower floor to add ModelDispatcher as an optional backend without forcing its
own users onto 3.12, the fix was to stop using syntax the floor doesn't
support rather than raise the floor to match the syntax:

- `type X = ...` → `X: TypeAlias = ...` (`typing.TypeAlias`, stdlib since
  3.10). `JSONValue` is self-referential, so its RHS stays a quoted string —
  the standard forward-reference form for a recursive alias pre-PEP-695;
  mypy resolves it identically either way.
- `def run_sync[T](...)` → an explicit module-level `_T = TypeVar("_T")`.
- `from typing import override` → `from typing_extensions import override`
  everywhere (works identically on every version `typing_extensions`
  supports, not just <3.12) — the package is now the one hard runtime
  dependency (`typing-extensions>=4.5`).

`StrEnum` (added in 3.11) was kept as-is rather than also chasing a 3.10
floor — replacing 6 enum classes to reach one more minor version wasn't worth
it against LangShift's own CI, which already tests on 3.11. If a future
consumer genuinely needs 3.10, that's the next thing to look at.
