# ModelDispatcher — Architecture

`ModelDispatcher` is a reusable internal library that acts as a central **AI Model
Gateway/Router**. A consuming application constructs one `ModelGateway` at
startup and dispatches every LLM/agent request through it. The gateway picks a
cost-appropriate model, transparently fails over on rate limits, runs a native
tool-calling loop, enforces per-tenant token quotas, validates a security
perimeter, and drives a two-stage onboarding flow.

> **Status:** working library. Routing, fallback, quota, the agent loop,
> security, and onboarding all run end-to-end against real provider adapters
> and pass `mypy --strict`, backed by a behavioral test suite and the
> interactive `demo/`. (This doc's class blueprints below predate the
> implementation and describe the intended shape; where behavior has since
> evolved beyond what's written here, the narrower
> [`docs/hld/hld.md`](docs/hld/hld.md) and [`docs/lld/lld.md`](docs/lld/lld.md)
> are kept current and win.)

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
(`OpenAIProvider`, `AnthropicProvider`, `GeminiProvider`) import their SDKs
lazily inside method bodies, keeping the core dependency-free.
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
4. `ModelInvocationHandler` — call the current candidate, rotating pooled
   credentials and folding in bounded transient retry *and* rate-limit
   failover: normally a rate limit moves straight to the next credential or
   provider, but when there's nowhere better to go it's retried instead,
   waiting for the provider's own "retry after" hint (capped at
   `rate_limit_max_wait`, default 120s) rather than failing outright.

`RateLimitHandler`/`RetryHandler` also exist in `fallback/handlers.py`, but as
**optional standalone links** for compositions that want those concerns
isolated — the default chain above folds both into step 4 instead, since they
wrap the same network call. See `docs/lld/lld.md` §7.2 for the exact
`_on_error` logic.

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
  4. chain = FallbackChain.build([Perimeter, Credential, Quota, ModelInvocation])
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

## Client-side integration & packaging layer

`demo/` (above) prototypes the consumption pattern in-repo: `demo/backend/app.py` maps any
`ModelDispatcherError` to `JSONResponse(status_code=exc.http_status, content=exc.to_payload())`
in one `except`, and `demo/frontend/src/api.ts` models the response as a `DispatchOutcome`
discriminated union that `App.tsx` switches on to open the key wizard. This section covers
the packaged, reusable version of that pattern — a publishable TypeScript client
([`clients/typescript`](./clients/typescript), `@joka-7/modeldispatcher-client`) and a
reference integration ([`templates/vercel-app`](./templates/vercel-app)) so any Next.js/React
app on Vercel can adopt the gateway by (a) dropping a thin Python wrapper into its `/api`
folder and (b) installing the client. It adds the two things the demo lacks for production:
a **cryptographic request perimeter** (Firebase App Check) at the Vercel edge, and a
**resilient network client** (timeouts, exponential backoff, structured 402/429 handling).

### Distribution

Both sides ship through **GitHub**, so a Vercel build needs exactly one credential (a GitHub
token) to fetch both — no private package index to stand up.

| Artifact | Channel | `requirements.txt` / `package.json` entry |
| --- | --- | --- |
| Python gateway library | Git URL pin | `model-dispatcher @ git+https://github.com/joka-7/ModelDispatcher@<tag>` |
| TypeScript client | GitHub Packages | `@joka-7/modeldispatcher-client` |

Both are distribution-agnostic at the call site: migrating later to a private PyPI + npm
registry changes only the dependency spec line — nothing in the wrapper or app code.

### Design patterns

| Layer | Pattern | Rationale |
| --- | --- | --- |
| `api/gateway.py` wrapper | **Adapter** (Vercel handler → library facade) + **Guard clause** (App Check) | Thin edge; no business logic |
| App Check verification | **Strategy** (`AppCheckVerifier` interface; real vs. dev-bypass impls) | Testable, env-swappable |
| TS network client | **Interceptor / Chain of Responsibility** (request + response interceptors) | Cross-cutting timeout/retry/error concerns composed, not tangled |
| TS retry | **Policy object** (`RetryPolicy`) | Backoff parameters injected, unit-testable |
| Handoff → UI | **Observer / pub-sub** (`GatewayEventBus`) + **discriminated union** result type | Decouples "402 arrived" from "which component renders the wizard" |
| React surface | **Custom hook** (`useGateway`) wrapping the event bus | Idiomatic; keeps components dumb |

### Directory layout

```
ModelDispatcher/
├── src/model_dispatcher/            # the gateway library (unchanged by this layer)
├── clients/
│   └── typescript/                  # publishable @joka-7/modeldispatcher-client
│       ├── package.json             # name, version, exports, react as optional peerDep
│       ├── tsconfig.json            # strict: true
│       └── src/
│           ├── index.ts             # public barrel
│           ├── types.ts             # STRICT interfaces: DispatchOutcome, Handoff, GatewayError…
│           ├── client.ts            # GatewayClient facade (create + dispatch)
│           ├── interceptors/
│           │   ├── interceptor.ts   # RequestInterceptor / ResponseInterceptor contracts
│           │   ├── timeout.ts       # AbortController-based request timeout
│           │   ├── retry.ts         # RetryPolicy + exponential backoff for 5xx
│           │   ├── appcheck.ts      # attaches X-Firebase-AppCheck token (request side)
│           │   └── handoff.ts       # detects 402/429 trigger_key_wizard, emits event
│           ├── events.ts            # GatewayEventBus (Observer)
│           └── react/
│               └── useGateway.ts    # React hook: dispatch() + wizard state
└── templates/
    └── vercel-app/                  # reference wiring teams copy
        ├── api/                     # ← Python runs here as Vercel Serverless Functions
        │   ├── requirements.txt     # model-dispatcher @ git+…@<tag>  (+ firebase-admin)
        │   ├── _lib/
        │   │   ├── __init__.py
        │   │   ├── appcheck.py      # AppCheckVerifier (Strategy) — verifies header token
        │   │   ├── wiring.py        # build_gateway(): ProviderRegistry + ModelGateway.create()
        │   │   └── http.py          # request parse + error→JSONResponse mapping helpers
        │   └── gateway.py           # THIN wrapper = Vercel handler (the invoke point)
        ├── app/ (or pages/)         # Next.js frontend
        │   ├── lib/gateway.ts       # createGatewayClient() configured for this app
        │   └── components/KeyWizard.tsx
        ├── package.json             # depends on @joka-7/modeldispatcher-client + firebase
        └── vercel.json              # function config (maxDuration); no pinned Python runtime
```

**Key placement fact:** on Vercel, any file under `/api` becomes a serverless function.
`api/gateway.py` *is* the HTTP endpoint (`POST /api/gateway`); the `requirements.txt` in that
folder is what Vercel's Python build installs. This is the mechanism that lets the frontend
and the packaged Python gateway co-deploy in a single project.

### Perimeter security — Firebase App Check

App Check proves a request originated from *your* genuine, unmodified frontend (via
reCAPTCHA / DeviceCheck / Play Integrity attestation) before any gateway logic runs. It lives
in the **thin wrapper**, not the library — the library's `PerimeterValidator` handles
tenant/size/allowlist concerns; App Check handles *client authenticity*.

- `api/_lib/appcheck.py` defines `AppCheckVerifier` as a `Protocol` (`verify(token) ->
  AppCheckClaims`, raising `AppCheckError` on failure) with a `FirebaseAppCheckVerifier`
  implementation that verifies the `X-Firebase-AppCheck` header via
  `firebase_admin.app_check.verify_token`.
- `api/gateway.py` is the wrapper: an Adapter with a leading guard clause — verify the
  header before touching the library at all; on failure, return `403 app_check_failed`
  without ever invoking the gateway; on success, parse the body into a `CompletionRequest` +
  `TenantContext` (the verified `uid` becomes the `TenantId`), dispatch, and map any
  `ModelDispatcherError` via `exc.http_status`/`exc.to_payload()` — reused verbatim from
  `demo/backend/app.py`'s one-liner.
- The App Check token is minted **client-side** by the Firebase SDK and attached by the TS
  `appcheck` interceptor — the developer never wires the header manually.
- Dev/local uses a `NoopAppCheckVerifier` (Strategy swap via env) so `demo/` and tests don't
  need Firebase.

### Network resilience — TypeScript interceptor client

`GatewayClient.dispatch()` runs each request through an ordered interceptor pipeline (Chain
of Responsibility): request side `[appcheck, timeout]`, response side `[retry, handoff]` —
retry runs first so a transient 5xx is retried before the body is ever interpreted as a
handoff.

- **timeout** — wraps each attempt in an `AbortController` firing at `timeoutMs`; abort →
  `NetworkError`.
- **appcheck** (request) — awaits `getToken()` from the Firebase App Check SDK; sets
  `X-Firebase-AppCheck`.
- **retry** (response/error) — on a status in `RetryPolicy.retryableStatuses` (`[500, 502,
  503, 504]` — **not** 402/429), sleeps `min(maxDelay, base·2^n)` with optional jitter and
  re-issues, up to `maxRetries`, so quota handoffs are never retried away.
- **handoff** (response) — the pivotal one: on `!res.ok`, reads the JSON body once; if
  `body.action` is a known handoff action (`trigger_key_wizard` / `upgrade_plan` /
  `retry_later`) it resolves to `{ kind: "handoff", ... }` **and publishes to the event
  bus**; otherwise `{ kind: "error", ... }`. This is where the Python `to_payload()`
  contract gets decoded.

`DispatchOutcome<T>` is the discriminated union every call resolves to: `"ok"` (result),
`"handoff"` (402/429 with a typed `Handoff`), `"error"` (a mapped `GatewayError`), or
`"network"` (timeout/offline/exhausted retries).

### GUI handoff — event bus + React hook

Goal: any component, anywhere in the tree, learns "render the key wizard now" without
prop-drilling the outcome from the dispatch call site.

1. **Decode** (the `handoff` interceptor) — on a non-OK response with a known `action`,
   build a typed `Handoff`, `eventBus.emit("handoff", { status, handoff })`, and resolve
   `dispatch()`'s own return value to `{ kind: "handoff", ... }`.
2. **Subscribe** (`useGateway` hook) — bridges the bus into React state: a `wizard` value
   set from the `"handoff"` event when its action is `trigger_key_wizard`, plus
   `dismissWizard()`.
3. **Render** (component) — `const { dispatch, wizard, dismissWizard } = useGateway();` then
   `{ wizard && <KeyWizard provider={wizard.provider} onClose={dismissWizard} /> }` —
   declarative, no HTTP knowledge.

Why an event bus rather than only a return value (the in-repo `demo/frontend` just lifts
state in `App.tsx`): in a real multi-page app, a 402 can surface from a background refresh
or a component far from the dispatch button. The bus lets a single top-level
`<KeyWizardHost/>` subscribe once and render the wizard regardless of which call triggered
it — while `dispatch()` **also** still returns the typed `DispatchOutcome` for call-site
handling. Both paths, one decode.

### Request/response cycle

```
[React component]
   │  useGateway().dispatch(prompt)
   ▼
[GatewayClient] request interceptors:
   appcheck → attaches X-Firebase-AppCheck (Firebase SDK getToken)
   timeout  → arms AbortController(timeoutMs)
   │  POST /api/gateway   { messages, … }
   ▼
──────────────── Vercel edge (same project) ────────────────
[api/gateway.py  (thin Adapter)]
   ① AppCheckVerifier.verify(header)  ──fail──▶ 403 app_check_failed  (library NOT invoked)
   ② parse → CompletionRequest, uid → TenantContext
   ③ ModelGateway.dispatch(req, tenant)      ← the packaged gateway library
        perimeter → triage → route → fallback chain → agent loop → quota commit
   ④ on ModelDispatcherError → JSONResponse(exc.http_status, exc.to_payload())
        e.g. QuotaExceededError → 402/429  { action: "trigger_key_wizard", provider, … }
   ⑤ success → 200 { final, steps, usage, … }
────────────────────────────────────────────────────────────
   ▼
[GatewayClient] response interceptors:
   retry   → 5xx? backoff + jitter, re-issue (≤ maxRetries).  402/429 pass through untouched.
   handoff → body.action known? → emit("handoff") + { kind: "handoff" }
   │
   ▼
[useGateway]  bus → setWizard(...)          [dispatch() caller] receives DispatchOutcome
   ▼
[<KeyWizardHost/>] renders <KeyWizard provider=… />
```

### Validation strategy

1. **TS client unit tests** (vitest) with a mocked `fetch`: 500 × 3 → one success after
   backoff; a 402 body `{action: "trigger_key_wizard"}` → `{kind: "handoff"}` **and** the
   event bus fires; timeout → `{kind: "network"}`; 402/429 are **not** retried.
2. **Wrapper unit tests** (pytest): missing/invalid App Check header → 403 and the gateway
   is never called (spy); a stubbed `QuotaExceededError` → 402/429 with the exact
   `trigger_key_wizard` payload.
3. **Template smoke run**: `vercel dev` on `templates/vercel-app/` with
   `NoopAppCheckVerifier`; dispatch until the free quota trips and confirm `<KeyWizard/>`
   mounts — the same behaviour as `demo/`, but through the packaged client and the
   `/api/gateway.py` path.
4. **Repo gates stay green**: `ruff check`, `mypy --strict src`, `pytest`, plus `tsc
   --noEmit` for the client.

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
