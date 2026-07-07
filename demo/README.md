# ModelDispatcher Demo (FastAPI + React)

An interactive console that exercises the gateway end-to-end with keyless
`MockProvider` strategies — no API keys required. It demonstrates all four
runtime features live in the browser:

- **Triage & routing** — the complexity badge shows which tier a prompt routed to.
- **Transparent fallback** — tick *Simulate primary rate-limit* to watch a
  rate-limited provider get intercepted and the request escalate to the next model.
- **Token-aware quota** — the meters fill as you dispatch; each call reserves and
  commits against the tenant's rolling windows.
- **Two-stage onboarding** — keep dispatching until the free-tier limit is hit and
  the gateway returns a `402`/`429` `trigger_key_wizard` payload, which the SPA
  renders as a key-wizard modal.

## Run locally (two processes)

Backend (from the repo root):

```bash
pip install -e .            # install the gateway library
pip install -r demo/backend/requirements.txt
uvicorn app:app --app-dir demo/backend --reload   # http://localhost:8000
```

Frontend (in another terminal):

```bash
cd demo/frontend
npm install
npm run dev                  # http://localhost:5173 (proxies /api to :8000)
```

## Run as a single container

The `Dockerfile` at the repo root builds the SPA, installs the library + backend,
and serves both from one image (FastAPI hosts the built assets):

```bash
docker build -t model-dispatcher-demo .
docker run --rm -p 8000:8000 model-dispatcher-demo   # http://localhost:8000
```

## API

| Method | Path            | Purpose                                              |
| ------ | --------------- | ---------------------------------------------------- |
| `POST` | `/api/dispatch` | Route + run a prompt; returns the trace or handoff.  |
| `GET`  | `/api/quota`    | Current per-tenant usage against each window.        |
| `GET`  | `/api/health`   | Liveness probe.                                      |

`/api/dispatch` returns `200` with a trace on success, or the gateway's chosen
status (`402` budget wall / `429` rate window / `403` perimeter) with the
structured error body on failure — the same contract a production app would map
to HTTP.
