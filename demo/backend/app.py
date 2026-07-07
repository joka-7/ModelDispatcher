"""FastAPI demo backend exposing the ModelDispatcher gateway.

This service wires a :class:`ModelGateway` in front of a small set of keyless
:class:`MockProvider` strategies so the whole pipeline — cost routing, transparent
fallback, token-aware quota, and the two-stage onboarding handoff — can be
exercised from a browser with no API keys.

The interesting mapping lives in :func:`dispatch`: every
:class:`ModelDispatcherError` already carries the HTTP status and JSON body a web
layer should surface, so translating a quota breach into a ``402``/``429``
``trigger_key_wizard`` response is a one-liner.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from model_dispatcher import (
    CompletionRequest,
    GatewaySettings,
    Message,
    ModelGateway,
    ModelTier,
    ProviderRegistry,
    QuotaDefaults,
    Role,
    TenantContext,
    TenantId,
    TenantQuota,
)
from model_dispatcher.exceptions import ModelDispatcherError
from model_dispatcher.providers import MockProvider
from model_dispatcher.quota.store import WINDOW_SECONDS, InMemoryQuotaStore
from model_dispatcher.routing.triage import TaskTriage

# A deliberately small per-tenant budget so the Stage-2 key wizard is reachable
# within a handful of demo requests.
_DEMO_QUOTA = TenantQuota(
    requests_per_min=30,
    tokens_per_min=400,
    tokens_per_day=4_000,
)
_SETTINGS = GatewaySettings(quota_defaults=QuotaDefaults())

# Shared, process-wide quota state so repeated calls from the UI accumulate
# toward the limit (the whole point of the onboarding demo).
_STORE = InMemoryQuotaStore()
_TRIAGE = TaskTriage()

app = FastAPI(title="ModelDispatcher Demo", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class DispatchBody(BaseModel):
    """Request payload for the ``/api/dispatch`` endpoint."""

    prompt: str = Field(min_length=1)
    tenant_id: str = "demo-tenant"
    simulate_rate_limit: bool = False


def _build_gateway(simulate_rate_limit: bool) -> ModelGateway:
    """Assemble a gateway over the demo providers, sharing the global store.

    When ``simulate_rate_limit`` is set, an always-rate-limited FREE provider is
    registered first so the fallback trace visibly escalates to the next model.
    """
    registry = ProviderRegistry()
    if simulate_rate_limit:
        registry.register(
            MockProvider("mock:free-overloaded", tier=ModelTier.FREE, fail_times=999)
        )
    registry.register(
        MockProvider("mock:free", tier=ModelTier.FREE, reply="[free tier] Done.")
    )
    registry.register(
        MockProvider(
            "mock:standard", tier=ModelTier.STANDARD, reply="[standard tier] Done."
        )
    )
    registry.register(
        MockProvider(
            "mock:premium",
            tier=ModelTier.PREMIUM,
            reply="[premium tier] Reasoned answer.",
        )
    )
    return ModelGateway.create(registry, settings=_SETTINGS, quota_store=_STORE)


def _tenant(tenant_id: str) -> TenantContext:
    return TenantContext(
        tenant_id=TenantId(tenant_id), quota=_DEMO_QUOTA, is_zero_setup=True
    )


@app.get("/api/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


@app.get("/api/quota")
def quota(tenant_id: str = "demo-tenant") -> dict[str, Any]:
    """Return the tenant's current usage against each rolling window."""
    tid = TenantId(tenant_id)
    windows = {
        "requests_per_min": _DEMO_QUOTA.requests_per_min,
        "tokens_per_min": _DEMO_QUOTA.tokens_per_min,
        "tokens_per_day": _DEMO_QUOTA.tokens_per_day,
    }
    return {
        "tenant_id": tenant_id,
        "windows": [
            {
                "name": name,
                "used": _STORE.read(tid, name),
                "limit": limit,
                "period_seconds": WINDOW_SECONDS[name],
            }
            for name, limit in windows.items()
        ],
    }


@app.post("/api/dispatch")
def dispatch(body: DispatchBody) -> JSONResponse:
    """Route and run a prompt, returning the trace or the onboarding handoff."""
    tenant = _tenant(body.tenant_id)
    request = CompletionRequest(
        messages=(Message(role=Role.USER, content=body.prompt),),
        tenant=tenant.tenant_id,
    )
    complexity = _TRIAGE.classify(request)
    gateway = _build_gateway(body.simulate_rate_limit)

    try:
        result = gateway.dispatch(request, tenant)
    except ModelDispatcherError as exc:
        # Every gateway error already knows its HTTP status and JSON body — this
        # is where the Stage-2 trigger_key_wizard payload reaches the browser.
        return JSONResponse(status_code=exc.http_status, content=exc.to_payload())

    steps = [
        {
            "message": step.message.content,
            "usage": step.usage.total_tokens,
            "attempts": [
                {
                    "provider": attempt.provider_name,
                    "error": attempt.error_class.value if attempt.error_class else None,
                }
                for attempt in step.attempts
            ],
        }
        for step in result.steps
    ]
    return JSONResponse(
        content={
            "final": result.final_message.content,
            "stop_reason": result.stop_reason.value,
            "complexity": complexity.name,
            "usage": {
                "prompt": result.usage.prompt_tokens,
                "completion": result.usage.completion_tokens,
                "total": result.usage.total_tokens,
            },
            "steps": steps,
        }
    )


# In a container image the built SPA is copied next to this file; mounting it last
# lets the API routes above take precedence over the static catch-all.
_STATIC_DIR = Path(os.environ.get("MD_STATIC_DIR", Path(__file__).parent / "static"))
if _STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")
