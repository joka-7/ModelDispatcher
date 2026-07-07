"""Credential resolution with a strict precedence chain.

The resolver decides *which* API credential a given request should use, and its
precedence order is the mechanical basis of the two-stage onboarding flow:
a user's own key is preferred, but its absence silently falls back to the shared,
rate-limited global app key so brand-new users get a zero-setup experience.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ..providers.base import ModelProvider
from ..quota.tenant import TenantContext

__all__ = ["CredentialSource", "Credential", "CredentialResolver"]


class CredentialSource(StrEnum):
    """Where a resolved credential originated (drives onboarding-stage decisions)."""

    USER = "user"
    TENANT = "tenant"
    GLOBAL_APP = "global_app"
    FREE_TIER = "free_tier"


@dataclass(frozen=True, slots=True)
class Credential:
    """A resolved credential plus the provenance the pipeline reasons about.

    Attributes:
        provider_name: Provider the credential authenticates against.
        source: Which tier of the precedence chain supplied it.
        secret_ref: Opaque reference/handle to the secret (never the raw key in
            logs; see :class:`SecretRedactor`).
        is_rate_limited: ``True`` for the shared global key, whose exhaustion is
            what triggers the Stage-2 handoff.
    """

    provider_name: str
    source: CredentialSource
    secret_ref: str
    is_rate_limited: bool = False


class CredentialResolver:
    """Resolves the credential to use for a tenant/provider pair.

    Precedence (first match wins):
        1. **User key** — the caller's own key for this provider.
        2. **Tenant key** — an organisation-wide key shared by the tenant.
        3. **Global app key** — the shared, rate-limited application key that
           powers the zero-setup stage.
        4. **Free tier** — a keyless free/local provider as the final safety net.
    """

    def resolve(self, tenant: TenantContext, provider: ModelProvider) -> Credential:
        """Return the highest-precedence credential available for the pair.

        Raises:
            AuthenticationError: If no credential of any tier can be resolved and
                the provider is not keyless.
        """
        raise NotImplementedError
