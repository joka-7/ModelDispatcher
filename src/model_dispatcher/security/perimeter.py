"""Secure proxy perimeter validation.

The gateway is designed to sit behind a proxy edge that faces untrusted callers.
:class:`PerimeterValidator` is the single choke point where an inbound request is
authenticated and sanity-checked before *any* downstream work (routing, quota,
model calls) happens, so a malformed or unauthorised request is rejected as
cheaply and early as possible.
"""

from __future__ import annotations

from ..config import SecuritySettings
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
        raise NotImplementedError
