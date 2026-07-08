"""The transport-agnostic dispatch pipeline.

Extracting the guard → adapt → invoke → map logic out of the Vercel handler makes
it a pure function of its inputs — no sockets, no globals — so it can be unit
tested directly and reused behind any transport. The handler in :mod:`api.gateway`
is then a thin I/O shell that reads the header and body and calls :func:`run_dispatch`.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from _lib.appcheck import AppCheckError, AppCheckVerifier
from _lib.auth import AuthError, AuthVerifier
from _lib.http import parse_dispatch_request, serialise_result
from _lib.wiring import build_gateway, build_tenant
from model_dispatcher import ModelGateway, TenantContext
from model_dispatcher.exceptions import ModelDispatcherError
from model_dispatcher.routing.triage import TaskTriage

GatewayFactory = Callable[[], ModelGateway]
TenantFactory = Callable[[str], TenantContext]

# Stateless; shared across requests the way `build_gateway`'s registry is.
_TRIAGE = TaskTriage()


def run_dispatch(
    *,
    app_check_token: str | None,
    authorization_header: str | None,
    raw_body: bytes,
    verifier: AppCheckVerifier,
    auth_verifier: AuthVerifier,
    gateway_factory: GatewayFactory = build_gateway,
    tenant_factory: TenantFactory = build_tenant,
    triage: TaskTriage = _TRIAGE,
) -> tuple[int, dict[str, Any]]:
    """Execute one dispatch and return the ``(status, json_body)`` to serialise.

    Algorithm:
        1. **Guard (app)** — ``verifier.verify`` the App Check token; on failure
           return ``403 app_check_failed`` and never build or call the gateway.
        2. **Guard (user)** — ``auth_verifier.verify`` the Authorization header;
           on failure return ``401 unauthenticated``. This is what makes tenant
           identity authoritative rather than a client-supplied string — see
           :mod:`_lib.auth`.
        3. **Adapt** — decode ``raw_body`` and validate it into a completion
           request; malformed input returns ``400 bad_request``. The tenant id
           actually used is the verified ``uid`` when auth is enforced, falling
           back to the request's declared ``tenant_id`` only when
           ``auth_verifier`` is the no-op (dev) strategy.
        4. **Invoke** — classify the request's complexity, build the gateway,
           and dispatch.
        5. **Map** — any :class:`ModelDispatcherError` becomes its own
           ``http_status`` + ``to_payload()`` (this is the Stage-2
           ``trigger_key_wizard`` path); success becomes ``200`` + the run
           trace, including the triaged ``complexity``.

    Args:
        app_check_token: Raw ``X-Firebase-AppCheck`` header value, if any.
        authorization_header: Raw ``Authorization`` header value, if any.
        raw_body: The undecoded request body bytes.
        verifier: The App Check strategy to enforce.
        auth_verifier: The Firebase Auth strategy to enforce.
        gateway_factory: Builds the gateway (injected for tests/spies).
        tenant_factory: Builds the tenant context from a tenant id.
        triage: Classifies request complexity for the response's ``complexity``
            field (injected for tests).

    Returns:
        A ``(status_code, body)`` pair ready for JSON serialisation.
    """
    try:
        verifier.verify(app_check_token)
    except AppCheckError:
        return 403, {"error": "app_check_failed"}

    try:
        claims = auth_verifier.verify(authorization_header)
    except AuthError:
        return 401, {"error": "unauthenticated"}

    try:
        decoded: Any = json.loads(raw_body or b"{}")
        if not isinstance(decoded, dict):
            raise ValueError("request body must be a JSON object")
        request, declared_tenant_id = parse_dispatch_request(decoded)
    except (ValueError, json.JSONDecodeError) as exc:
        return 400, {"error": "bad_request", "detail": str(exc)}

    tenant_id = claims.uid or declared_tenant_id
    tenant = tenant_factory(tenant_id)
    complexity = triage.classify(request).name
    try:
        result = gateway_factory().dispatch(request, tenant)
    except ModelDispatcherError as exc:
        return exc.http_status, exc.to_payload()

    return 200, serialise_result(result, complexity)
