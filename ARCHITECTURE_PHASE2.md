# ModelDispatcher — Architecture, Phase 2

**Client-Side Integration & Packaging Layer**

Phase 1 (see [`ARCHITECTURE.md`](./ARCHITECTURE.md)) delivered `model-dispatcher`: a
self-contained Python ≥3.12 gateway library whose public surface is a single facade —
`ModelGateway.dispatch()` (`src/model_dispatcher/gateway.py`) — and an HTTP-aware exception
hierarchy where **every** error carries `http_status` + `to_payload()`
(`src/model_dispatcher/exceptions.py`). The terminal onboarding signal, `QuotaExceededError`,
wraps a `HandoffResponse` (`src/model_dispatcher/onboarding/handoff.py`) that serialises to the
exact contract the UI must react to:

```json
{"error": "quota_exceeded", "provider": "openai", "action": "trigger_key_wizard"}
```

The in-repo `demo/` already prototypes the consumption pattern end-to-end: `demo/backend/app.py`
maps any `ModelDispatcherError` to `JSONResponse(status_code=exc.http_status, content=exc.to_payload())`
in one `except`, and `demo/frontend/src/api.ts` models the response as a `DispatchOutcome`
discriminated union that `App.tsx` switches on to open the key wizard.

**Phase 2's job** is to take that proven demo pattern and turn it into a *reusable, hardened,
deployable* integration layer, so that *any* Next.js/React app on **Vercel** can adopt the gateway
by (a) dropping a thin Python wrapper into its `/api` folder and (b) installing one typed TypeScript
client. It adds the two things the demo lacks for production: a **cryptographic request perimeter**
(Firebase App Check) at the Vercel edge, and a **resilient network client** (timeouts, exponential
backoff, structured 402/429 handling).

> **Status:** implemented. This document is the original design proposal — interfaces, signatures,
> directory layout, and the request/response flow — written before any of it existed. It's kept as
> the *rationale* record; for what actually shipped, treat it as a close-but-not-exact map and go to
> the real thing: [`clients/typescript`](./clients/typescript) (`@joka-7/modeldispatcher-client`) and
> [`templates/vercel-app`](./templates/vercel-app) (the Next.js + Vercel Python Function reference
> app), both with their own READMEs. Known drift from this doc: `vercel.json` no longer pins a Python
> runtime version below (Vercel resolves it from the project settings instead), and the Python floor
> referenced throughout is `>=3.11`, not `>=3.12` — see `ARCHITECTURE.md`'s "Lowering the Python
> floor" note.

---

## Distribution decisions

Both sides ship through **GitHub**, so a Vercel build needs exactly one credential (a GitHub token)
to fetch both — no private package index to stand up.

| Artifact | Channel | `requirements.txt` / `package.json` entry |
| --- | --- | --- |
| Python gateway library | Git URL pin | `model-dispatcher @ git+https://github.com/joka-7/ModelDispatcher@v0.2.0` |
| TypeScript client | GitHub Packages / git dependency | `@joka-7/modeldispatcher-client` |

Both are distribution-agnostic at the call site: migrating later to a private PyPI + npm registry
changes only the dependency spec line — nothing in the wrapper or app code. The existing `demo/`
folder is retained as the keyless local playground.

## Design patterns

| Layer | Pattern | Rationale |
| --- | --- | --- |
| `api/gateway.py` wrapper | **Adapter** (Vercel handler → library facade) + **Guard clause** (App Check) | Thin edge; no business logic |
| App Check verification | **Strategy** (`AppCheckVerifier` interface; real vs. dev-bypass impls) | Testable, env-swappable |
| TS network client | **Interceptor / Chain of Responsibility** (request + response interceptors) | Cross-cutting timeout/retry/error concerns composed, not tangled |
| TS retry | **Policy object** (`RetryPolicy`) | Backoff parameters injected, unit-testable |
| Handoff → UI | **Observer / pub-sub** (`GatewayEventBus`) + **discriminated union** result type | Decouples "402 arrived" from "which component renders the wizard" |
| React surface | **Custom hook** (`useGateway`) wrapping the event bus | Idiomatic; keeps components dumb |

---

## Directory layout

Repo-level additions (the Phase 1 library under `src/` is unchanged):

```
ModelDispatcher/
├── src/model_dispatcher/            # Phase 1 library (unchanged)
├── clients/
│   └── typescript/                  # NEW — publishable @joka-7/modeldispatcher-client
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
    └── vercel-app/                  # NEW — reference wiring teams copy
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
        └── vercel.json              # runtime pins (python3.12), function config
```

**Key placement fact:** on Vercel, any file under `/api` becomes a serverless function. `api/gateway.py`
*is* the HTTP endpoint (`POST /api/gateway`); the `requirements.txt` in that folder is what Vercel's
Python build installs. This is the mechanism that lets the frontend and the packaged Python gateway
co-deploy in a single project.

---

## Perimeter security — Firebase App Check

App Check proves a request originated from *your* genuine, unmodified frontend (via
reCAPTCHA / DeviceCheck / Play Integrity attestation) before any gateway logic runs. It lives in the
**thin wrapper**, not the library — the library's `PerimeterValidator` handles tenant/size/allowlist
concerns; App Check handles *client authenticity*.

**`api/_lib/appcheck.py`** (PEP 8, full docstrings and annotations):

```python
class AppCheckVerifier(Protocol):
    def verify(self, token: str | None) -> AppCheckClaims: ...   # raises AppCheckError on failure

class FirebaseAppCheckVerifier:
    """Verifies the X-Firebase-AppCheck header via firebase_admin.app_check.verify_token."""
    def verify(self, token: str | None) -> AppCheckClaims: ...
```

**`api/gateway.py`** — the wrapper, as an Adapter with a leading guard clause:

```python
def handler(request):                                  # Vercel Python entrypoint
    # 1. GUARD: cryptographically verify the caller BEFORE touching the library
    try:
        _VERIFIER.verify(request.headers.get("X-Firebase-AppCheck"))
    except AppCheckError:
        return json_response(403, {"error": "app_check_failed"})
    # 2. Parse body → CompletionRequest + TenantContext (uid from App Check claims → tenant)
    # 3. gateway = build_gateway();  result = gateway.dispatch(req, tenant)
    # 4. except ModelDispatcherError as exc:
    #        return json_response(exc.http_status, exc.to_payload())   # one-liner, reused from demo
    # 5. return json_response(200, serialise(result))
```

Design points:

- The App Check token is minted **client-side** by the Firebase SDK and attached by the TS `appcheck`
  interceptor — the developer never wires the header manually.
- Verification failure short-circuits to `403 app_check_failed` and the library is **never invoked** —
  perimeter defense before compute spend.
- Dev/local uses a `NoopAppCheckVerifier` (Strategy swap via env) so `demo/` and tests do not need Firebase.
- The verified Firebase `uid` maps to the gateway's `TenantId`, unifying edge identity with the library's
  multi-tenant quota model.

---

## Network resilience — TypeScript interceptor client

`GatewayClient.dispatch()` runs each request through an ordered interceptor pipeline (Chain of
Responsibility). **Strict interfaces** (`clients/typescript/src/types.ts`):

```ts
export interface GatewayRequestConfig {
  url: string;
  body: unknown;
  timeoutMs: number;
  signal?: AbortSignal;
  headers: Record<string, string>;
}
export interface RequestInterceptor  { onRequest(cfg: GatewayRequestConfig): Promise<GatewayRequestConfig>; }
export interface ResponseInterceptor { onResponse(res: Response): Promise<Response>;
                                        onError?(err: unknown, cfg: GatewayRequestConfig): Promise<Response>; }

export interface RetryPolicy {
  maxRetries: number;      // e.g. 3
  baseDelayMs: number;     // e.g. 250
  maxDelayMs: number;      // cap
  jitter: boolean;         // full-jitter to avoid a thundering herd
  retryableStatuses: readonly number[];   // [500, 502, 503, 504]  — NOT 402/429
}

export type DispatchOutcome<T> =        // mirrors demo/frontend/src/api.ts, generalised
  | { kind: "ok"; result: T }
  | { kind: "handoff"; status: number; handoff: Handoff }   // 402 | 429 trigger_key_wizard
  | { kind: "error"; status: number; error: GatewayError }
  | { kind: "network"; error: NetworkError };               // timeout / offline / exhausted retries

export interface Handoff {
  error: "quota_exceeded" | string;
  provider: string;
  action: "trigger_key_wizard" | "upgrade_plan" | "retry_later";
  detail?: string;
}
```

Interceptor responsibilities:

- **timeout.ts** — wraps each attempt in an `AbortController` firing at `timeoutMs`; abort → `NetworkError`.
- **appcheck.ts** (request) — `await getToken()` from the Firebase App Check SDK; sets `X-Firebase-AppCheck`.
- **retry.ts** (response/error) — on a status in `retryableStatuses`, sleep `min(maxDelay, base·2^n)` (+ jitter)
  and re-issue, up to `maxRetries`; **explicitly excludes 402/429** so quota handoffs are never retried away.
- **handoff.ts** (response) — the pivotal one: on `!res.ok`, read JSON once; if `body.action` is a known
  handoff action → resolve to `{ kind: "handoff", … }` **and publish to the event bus**; otherwise
  `{ kind: "error", … }`. This is where the Python `to_payload()` contract is decoded.

Ordering: request side `[appcheck, timeout]`; response side `[retry, handoff]` — retry runs first so a
transient 5xx is retried before we ever try to interpret the body as a handoff.

---

## GUI handoff state management

Goal: any component, anywhere in the tree, learns "render the key wizard now" **without prop-drilling**
the outcome from the dispatch call site. Uses Observer + a React hook.

Conceptual algorithm:

```
// 1. DECODE (handoff.ts interceptor) — turn the raw 402/429 body into typed state
on response where !res.ok:
    payload ← res.json()
    if payload.action ∈ {trigger_key_wizard, upgrade_plan, retry_later}:
        handoff ← { error, provider, action, detail } as Handoff
        eventBus.emit("handoff", { status: res.status, handoff })   // BUBBLE UP (pub/sub)
        return { kind: "handoff", status, handoff }
    else:
        return { kind: "error", status, error: parseError(payload) }

// 2. SUBSCRIBE (useGateway hook) — bridge the bus into React state
useGateway():
    wizard ← useState<null | { provider, status, action }>(null)
    useEffect: unsub ← eventBus.on("handoff", e =>
        if e.handoff.action == "trigger_key_wizard": setWizard({ provider, status, action }))
    return { dispatch, wizard, dismissWizard: () => setWizard(null) }

// 3. RENDER (component) — declarative, knows nothing about HTTP
const { dispatch, wizard, dismissWizard } = useGateway();
{ wizard && <KeyWizard provider={wizard.provider} onClose={dismissWizard} /> }
```

Why an event bus rather than only a return value (the demo returns the outcome and lifts state in
`App.tsx`): in a real multi-page app, a 402 can surface from a background refresh or a component far from
the dispatch button. The bus lets a *single* top-level `<KeyWizardHost/>` subscribe once and render the
wizard regardless of which call triggered it — while `dispatch()` **also** still returns the typed
`DispatchOutcome` for call-site handling. Both paths, one decode.

---

## Request / response cycle

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
   ③ ModelGateway.dispatch(req, tenant)      ← Phase 1 library (git-pinned in requirements.txt)
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

---

## Code quality conventions

- **Backend wrapper (`api/`)**: PEP 8 under the repo's existing `ruff` config (E, W, F, I, N, UP, B, D)
  and `mypy --strict`; Google-style docstrings with an *Algorithm* section on non-trivial functions;
  full type annotations. `AppCheckVerifier` as a `Protocol` mirrors the library's `QuotaStore` /
  `MetricsSink` seams.
- **TypeScript client**: `tsconfig` `strict: true`; every public boundary a named `interface` or
  discriminated union; no `any` (`unknown` + narrowing); TSDoc on all exports; interceptors and policies
  are injected, not hard-coded.
- **Reuse, do not reinvent**: the wrapper's error handling is the demo's proven one-liner
  (`demo/backend/app.py`); the TS `DispatchOutcome` / `Handoff` types generalise
  `demo/frontend/src/api.ts`; the wizard-open logic generalises `demo/frontend/src/App.tsx`.

---

## Validation strategy

1. **TS client unit tests** (vitest) with a mocked `fetch`: assert (a) 500 × 3 → one success after
   backoff, (b) a 402 body `{action: "trigger_key_wizard"}` → `{kind: "handoff"}` **and** the event bus
   fired, (c) timeout → `{kind: "network"}`, (d) 402/429 are **not** retried.
2. **Wrapper unit tests** (pytest): missing/invalid App Check header → 403 and the gateway is never called
   (spy); a stubbed `QuotaExceededError` → 402/429 with the exact `trigger_key_wizard` payload.
3. **Template smoke run**: `vercel dev` on `templates/vercel-app/` with `NoopAppCheckVerifier`; dispatch
   until the free quota trips and confirm the `<KeyWizard/>` mounts — reproducing the current `demo/`
   behaviour but through the packaged client and the `/api/gateway.py` path.
4. **Repo gates stay green**: `ruff check`, `mypy --strict src`, `pytest`, plus `tsc --noEmit` for the client.
