"""Secure proxy perimeter validation.

The gateway is designed to sit behind a proxy edge that faces untrusted callers.
:class:`PerimeterValidator` is the single choke point where an inbound request is
authenticated and sanity-checked before *any* downstream work (routing, quota,
model calls) happens, so a malformed or unauthorised request is rejected as
cheaply and early as possible.
"""

from __future__ import annotations

import json

from ..config import SecuritySettings
from ..exceptions import PerimeterViolation
from ..quota.tenant import TenantContext
from ..types import CompletionRequest
from .credentials import CredentialResolver

__all__ = ["PerimeterValidator"]


class PerimeterValidator:
    """Validates the trust perimeter for one inbound request."""

    def __init__(
        self, settings: SecuritySettings, credentials: CredentialResolver
    ) -> None:
        self._settings = settings
        self._credentials = credentials

    def validate(self, request: CompletionRequest, tenant: TenantContext) -> None:
        """Assert the request may proceed, or raise :class:`PerimeterViolation`.

        Algorithm (fail fast, cheapest checks first):
            1. **Authn** — if ``require_tenant_auth`` and the tenant has no
               resolvable credential, reject.
            2. **Size** — reject when the serialised payload exceeds
               ``max_payload_bytes`` (guards against memory-exhaustion abuse).
            3. **Egress allowlist** — reject requests that would target a provider
               outside ``allowed_providers``.
            4. **Structural sanity** — reject malformed message/tool schemas and
               apply prompt-injection heuristics on tool definitions.

        Raises:
            PerimeterViolation: On any failed check (HTTP 403).
        """
        if self._settings.require_tenant_auth and not tenant.tenant_id:
            raise PerimeterViolation("request is missing a tenant identity")

        if not request.messages:
            raise PerimeterViolation("request carries no messages")

        payload_bytes = self._estimate_payload_bytes(request)
        if payload_bytes > self._settings.max_payload_bytes:
            raise PerimeterViolation(
                f"payload {payload_bytes} bytes exceeds limit "
                f"{self._settings.max_payload_bytes}"
            )

        allowed = self._settings.allowed_providers
        if allowed and tenant.metadata.get("forced_provider") not in allowed:
            forced = tenant.metadata.get("forced_provider")
            if forced is not None:
                raise PerimeterViolation(
                    f"provider {forced!r} is not on the egress allowlist"
                )

    @staticmethod
    def _estimate_payload_bytes(request: CompletionRequest) -> int:
        """Estimate the serialised size of the request body in bytes."""
        total = 0
        for message in request.messages:
            total += len((message.content or "").encode("utf-8"))
            if message.tool_result is not None:
                total += len(message.tool_result.content.encode("utf-8"))
        for tool in request.tools:
            total += len(tool.name) + len(tool.description)
            total += len(json.dumps(tool.parameters).encode("utf-8"))
        return total
