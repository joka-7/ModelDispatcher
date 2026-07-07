# Firebase App Check setup

This is a step-by-step console checklist for standing up the Firebase project
this template's perimeter needs. It's manual console work only you can do (it
needs your Google account), so nothing here can be automated on your behalf —
follow it once, and the code side (already wired in this template) picks it up
through the env vars below.

Budget ~15 minutes. You'll end up with six values that map directly onto
[`.env.example`](./.env.example).

## What you're building

```
Browser (Firebase App Check SDK)
   │  attests this is your real, unmodified frontend
   │  (reCAPTCHA v3 → attestation token)
   ▼
POST /api/gateway   header: X-Firebase-AppCheck: <token>
   ▼
api/_lib/appcheck.py  verifies the token via firebase-admin
   │  valid  → invoke the gateway
   │  invalid/missing → 403 app_check_failed (gateway never runs)
```

Two separate Firebase artifacts are involved: a **Web App registration**
(gives you the public `NEXT_PUBLIC_FIREBASE_*` config) and a **service account**
(gives the *backend* the private credential to verify tokens). Mixing these up
is the most common setup mistake — the web app config is safe to ship to the
browser; the service account key is not.

## 1. Create or select a Firebase project

1. Go to the [Firebase console](https://console.firebase.google.com/) and
   click **Add project** (or pick an existing one).
2. Google Analytics is optional for this integration — skip it unless you want
   it for other reasons.

## 2. Register a Web App

1. In the project overview, click the **Web** icon (`</>`) to add a web app.
2. Give it a nickname (e.g. "vercel-app"). You don't need Firebase Hosting.
3. Firebase shows a `firebaseConfig` object. Copy four fields into
   `.env.local` (see [`.env.example`](./.env.example)):

   | `firebaseConfig` key | `.env.local` var |
   | --- | --- |
   | `apiKey` | `NEXT_PUBLIC_FIREBASE_API_KEY` |
   | `authDomain` | `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN` |
   | `projectId` | `NEXT_PUBLIC_FIREBASE_PROJECT_ID` |
   | `appId` | `NEXT_PUBLIC_FIREBASE_APP_ID` |

   These are public identifiers, not secrets — they're meant to ship in the
   browser bundle (App Check is what prevents abuse, not hiding this config).

## 3. Get a reCAPTCHA v3 site key

App Check's web attestation provider (`ReCaptchaV3Provider`, already wired in
`app/lib/gateway.ts`) needs a reCAPTCHA v3 site key.

1. Go to the [reCAPTCHA admin console](https://www.google.com/recaptcha/admin/create).
2. Register a new site:
   - **reCAPTCHA type**: reCAPTCHA v3.
   - **Domains**: add `localhost` (for local dev) and every domain this app
     will actually be served from — your Vercel production domain
     (`your-app.vercel.app` or a custom domain) and, if you want preview
     deployments to work too, `*.vercel.app` isn't accepted as a wildcard here,
     so add specific preview domains as you learn them, or re-test locally.
3. Copy the **Site key** (not the secret key — App Check's client SDK only
   needs the site key).

## 4. Enable App Check for the Web App

1. In the Firebase console, go to **Build → App Check**.
2. Click **Get started**, then find your web app in the app list and
   **Register**.
3. Choose **reCAPTCHA v3** as the provider and paste in the site key from
   step 3.
4. Set `NEXT_PUBLIC_FIREBASE_APPCHECK_SITE_KEY` in `.env.local` to that same
   site key.

You do **not** need to toggle "Enforce" for any Firebase product (Firestore,
Functions, etc.) — this template doesn't use those. Verification happens in
*our own* backend (`api/_lib/appcheck.py` via `firebase-admin`), not through
Firebase's per-product enforcement switches. The App Check console is still
useful afterwards: **App Check → Apps → your app → Metrics** shows a live
verified/unverified request breakdown once traffic starts flowing.

## 5. Create a service-account credential for the backend

The Python function verifies tokens with the **Firebase Admin SDK**, which
needs its own credential — separate from the public web config above.

1. In the Firebase console, click the gear icon → **Project settings**.
2. Go to the **Service accounts** tab.
3. Click **Generate new private key**. This downloads a JSON file — treat it
   like a password; never commit it.
4. Configure the backend to use it, depending on where you're running:

   **Local dev** — point `GOOGLE_APPLICATION_CREDENTIALS` at the file:

   ```
   GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/service-account.json
   ```

   **Vercel (no persistent filesystem for a file path)** — paste the JSON
   contents directly into a `FIREBASE_SERVICE_ACCOUNT_JSON` env var instead
   (this is what `api/_lib/appcheck.py` checks first). To avoid shell/dashboard
   quoting issues, base64-encode it before pasting:

   ```bash
   base64 -i service-account.json | pbcopy   # macOS; use -w0 on Linux + xclip
   ```

   Then in the Vercel dashboard (**Project → Settings → Environment
   Variables**), add `FIREBASE_SERVICE_ACCOUNT_JSON` with that base64 string
   for the Production/Preview environments you deploy to. The backend accepts
   either raw or base64-encoded JSON, so this "just works" either way.

## 6. Verify locally

```bash
# App Check enforced, using the real Firebase project you just configured:
vercel dev

# Dispatch a prompt from the UI. A valid token should sail through; try
# clearing site data / using a different browser profile to see a 403
# app_check_failed if attestation fails.
```

To iterate on everything *except* the perimeter (no Firebase project needed
yet), bypass it explicitly:

```bash
MD_APP_CHECK_MODE=disabled vercel dev
```

Never set `MD_APP_CHECK_MODE=disabled` in a deployed environment — it accepts
every request unverified.

## Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| `403 app_check_failed` on every request | Site key mismatch between step 3/4, or the domain making the request isn't in the reCAPTCHA site's allowed domains (step 3). |
| Backend raises about the default Firebase app / credentials | Neither `FIREBASE_SERVICE_ACCOUNT_JSON` nor `GOOGLE_APPLICATION_CREDENTIALS` is set/reachable in that environment (step 5). |
| Works locally, 403s only on Vercel | You configured `GOOGLE_APPLICATION_CREDENTIALS` (a file path) instead of `FIREBASE_SERVICE_ACCOUNT_JSON` for the deployed environment — Vercel functions have no persistent file to point at. |
| Works on `vercel dev`, fails on a Preview deployment | The preview's domain isn't in the reCAPTCHA site's allowed domains list (step 3) — add it and redeploy. |

## Summary: six values, two sources

| Var | From |
| --- | --- |
| `NEXT_PUBLIC_FIREBASE_API_KEY` | Web app config (step 2) |
| `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN` | Web app config (step 2) |
| `NEXT_PUBLIC_FIREBASE_PROJECT_ID` | Web app config (step 2) |
| `NEXT_PUBLIC_FIREBASE_APP_ID` | Web app config (step 2) |
| `NEXT_PUBLIC_FIREBASE_APPCHECK_SITE_KEY` | reCAPTCHA site key (step 3) |
| `GOOGLE_APPLICATION_CREDENTIALS` *or* `FIREBASE_SERVICE_ACCOUNT_JSON` | Service account key (step 5) |
