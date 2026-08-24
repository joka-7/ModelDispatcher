# ModelDispatcher — Vercel integration template

A minimal Next.js (App Router) app that runs the **ModelDispatcher** gateway as a
Vercel Python Function behind a Firebase App Check + Auth perimeter, and talks to
it from the browser through the resilient `@joka-7/modeldispatcher-client`. App
Check attests the app instance; Firebase Auth (anonymous by default) attests the
end user and is what makes per-tenant quota isolation real — the wrapper derives
the tenant id from the verified `uid`, not from anything the client claims.

This is the reference wiring described in [`ARCHITECTURE.md`](../../ARCHITECTURE.md)'s
"Client-side integration & packaging layer" section. Copy the folder, set your env vars,
and deploy.

## Layout

```
vercel-app/
├── api/                     # Python — becomes Vercel Serverless Functions
│   ├── gateway.py           # POST /api/gateway — thin handler (I/O shell)
│   ├── requirements.txt     # git-pinned model-dispatcher + firebase-admin
│   ├── _lib/
│   │   ├── firebase_app.py  # shared firebase_admin bootstrap (App Check + Auth)
│   │   ├── appcheck.py      # AppCheckVerifier strategy (Firebase / Noop)
│   │   ├── auth.py          # AuthVerifier strategy — verified uid -> tenant id
│   │   ├── wiring.py        # build_gateway(): providers + ModelGateway.create()
│   │   ├── http.py          # request parse / result serialise
│   │   └── pipeline.py      # guard → guard → adapt → invoke → map (pure, testable)
│   └── tests/               # pytest for the pipeline
├── app/                     # Next.js frontend
│   ├── lib/gateway.ts       # GatewayClient singleton wired to App Check + Auth
│   ├── components/KeyWizard.tsx
│   ├── page.tsx             # dispatch console + outcome rendering
│   └── layout.tsx
├── package.json             # @joka-7/modeldispatcher-client + firebase + next
├── vercel.json              # function config
└── .env.example
```

## Request/response flow

```
useGateway().dispatch(prompt)
  → GatewayClient  [appcheck → auth → retry → timeout → fetch]  POST /api/gateway
  → api/gateway.py [App Check guard → Auth guard → parse → ModelGateway.dispatch
                     → error map]
  → GatewayClient  [retry 5xx / decode 402|429 handoff]
  → useGateway     [handoff event → wizard state]  +  DispatchOutcome to caller
  → <KeyWizard/>   renders when a trigger_key_wizard handoff arrives
```

The tenant id used for quota is the verified Firebase Auth `uid`, not anything
the request body claims — see `api/_lib/auth.py`.

## Setup

1. **Install deps**

   ```bash
   npm install
   ```

2. **Configure env** — copy `.env.example` to `.env.local` and fill in your
   Firebase project + App Check reCAPTCHA site key. Never set up a Firebase
   project before? [`FIREBASE_APPCHECK_SETUP.md`](./FIREBASE_APPCHECK_SETUP.md)
   is a from-scratch console checklist (~15 minutes) covering exactly the six
   env vars this template needs.

3. **Backend credential** — the Python function verifies App Check tokens *and*
   Firebase Auth ID tokens with `firebase-admin`, sharing one bootstrap. Set
   `GOOGLE_APPLICATION_CREDENTIALS` (a file path, for local dev) or
   `FIREBASE_SERVICE_ACCOUNT_JSON` (the credential JSON itself, for Vercel —
   see the setup doc for why).

   Enable **Anonymous** sign-in for your Firebase project (Console → Build →
   Authentication → Sign-in method) — the reference frontend signs users in
   anonymously by default so there's a stable per-browser identity with no
   login form.

4. **Pin the gateway** — edit `api/requirements.txt` to the tag/commit you want:

   ```
   model-dispatcher @ git+https://github.com/joka-7/ModelDispatcher@v0.2.0
   ```

## Local development

```bash
# Bypass both guards locally (no Firebase needed) and run both layers:
MD_APP_CHECK_MODE=disabled MD_AUTH_MODE=disabled vercel dev
```

With `MD_AUTH_MODE=disabled`, the tenant id falls back to the request body's own
`tenant_id` (defaulting to `"anonymous"`) — the pre-auth behaviour. Never set
this in a deployed environment: without a verified `uid`, any caller can pick an
arbitrary tenant and dodge (or exhaust someone else's) quota.

The shipped `wiring.py` uses keyless mock providers, so a fresh checkout runs end
to end. Dispatch repeatedly to exhaust the small demo quota and watch the
`KeyWizard` open from the Stage-2 `trigger_key_wizard` handoff.

### Going live per tier

`api/_lib/wiring.py` fills each of the three routing tiers (`FREE`/`STANDARD`/
`PREMIUM`) from `_SLOTS`: if that tier's API key env var is set, it registers the
real adapter (`GeminiProvider` / `OpenAIProvider` / `AnthropicProvider`); if not,
it falls back to the keyless mock. No code changes needed — set the keys you have
and leave the rest unset:

| Tier | Env var | Model override | Adapter |
| --- | --- | --- | --- |
| FREE | `MD_GEMINI_API_KEY` | `MD_GEMINI_MODEL` | `GeminiProvider` |
| STANDARD | `MD_OPENAI_API_KEY` | `MD_OPENAI_MODEL` | `OpenAIProvider` |
| PREMIUM | `MD_ANTHROPIC_API_KEY` | `MD_ANTHROPIC_MODEL` | `AnthropicProvider` |

Also add the matching extra(s) to `api/requirements.txt` (e.g.
`model-dispatcher[openai]`) so the vendor SDK you actually key is installed —
extras you don't use add cold-start weight for nothing.

## Tests

```bash
# Backend pipeline (Python >= 3.11, gateway installed):
pip install -e ../..          # installs model-dispatcher from the repo root
pytest api/tests

# Frontend typecheck:
npm run typecheck
```

## Going to production

- Set `MD_APP_CHECK_MODE=enforce` and `MD_AUTH_MODE=enforce` (both the default)
  so every request is attested *and* the tenant id is a verified `uid` — never
  disable either in a deployed environment.
- The reference wiring signs users in anonymously (`app/lib/gateway.ts`), which
  is enough for stable per-browser quota isolation with no login form. Swap in
  a real sign-in flow (email/password, OAuth, etc.) if the product needs actual
  user accounts — `authTokenProvider` just needs a valid Firebase Auth ID token
  from whatever flow you use.
- Move distribution to a private PyPI + npm registry by changing only the
  `requirements.txt` line and the `package.json` dependency — no code changes.
