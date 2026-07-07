# ModelDispatcher — Vercel integration template

A minimal Next.js (App Router) app that runs the **ModelDispatcher** gateway as a
Vercel Python Function behind a Firebase App Check perimeter, and talks to it from
the browser through the resilient `@joka-7/modeldispatcher-client`.

This is the Phase 2 reference wiring described in
[`ARCHITECTURE_PHASE2.md`](../../ARCHITECTURE_PHASE2.md). Copy the folder, set your
env vars, and deploy.

## Layout

```
vercel-app/
├── api/                     # Python — becomes Vercel Serverless Functions
│   ├── gateway.py           # POST /api/gateway — thin handler (I/O shell)
│   ├── requirements.txt     # git-pinned model-dispatcher + firebase-admin
│   ├── _lib/
│   │   ├── appcheck.py      # AppCheckVerifier strategy (Firebase / Noop)
│   │   ├── wiring.py        # build_gateway(): providers + ModelGateway.create()
│   │   ├── http.py          # request parse / result serialise
│   │   └── pipeline.py      # guard → adapt → invoke → map (pure, testable)
│   └── tests/               # pytest for the pipeline
├── app/                     # Next.js frontend
│   ├── lib/gateway.ts       # GatewayClient singleton wired to App Check
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
  → GatewayClient  [appcheck → retry → timeout → fetch]   POST /api/gateway
  → api/gateway.py [App Check guard → parse → ModelGateway.dispatch → error map]
  → GatewayClient  [retry 5xx / decode 402|429 handoff]
  → useGateway     [handoff event → wizard state]  +  DispatchOutcome to caller
  → <KeyWizard/>   renders when a trigger_key_wizard handoff arrives
```

## Setup

1. **Install deps**

   ```bash
   npm install
   ```

2. **Configure env** — copy `.env.example` to `.env.local` and fill in your
   Firebase project + App Check reCAPTCHA site key. Enable App Check for your
   Firebase app and register the reCAPTCHA v3 provider.

3. **Backend credential** — the Python function verifies App Check tokens with
   `firebase-admin`, which needs Application Default Credentials. Set
   `GOOGLE_APPLICATION_CREDENTIALS` (local) or add the Vercel Firebase
   integration / a service-account secret (deploy).

4. **Pin the gateway** — edit `api/requirements.txt` to the tag/commit you want:

   ```
   model-dispatcher @ git+https://github.com/joka-7/ModelDispatcher@v0.2.0
   ```

## Local development

```bash
# Bypass App Check locally (no Firebase needed) and run both layers:
MD_APP_CHECK_MODE=disabled vercel dev
```

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
# Backend pipeline (Python >= 3.12, gateway installed):
pip install -e ../..          # installs model-dispatcher from the repo root
pytest api/tests

# Frontend typecheck:
npm run typecheck
```

## Going to production

- Set `MD_APP_CHECK_MODE=enforce` (the default) so every request is attested.
- For per-user identity (not just app attestation), pair App Check with a
  Firebase Auth ID token and derive the tenant from its `uid` in
  `api/_lib/http.py`.
- Move distribution to a private PyPI + npm registry by changing only the
  `requirements.txt` line and the `package.json` dependency — no code changes.
