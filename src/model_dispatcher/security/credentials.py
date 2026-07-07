"""Credential resolution with a strict precedence chain.

The resolver decides *which* API credential a given request should use, and its
precedence order is the mechanical basis of the two-stage onboarding flow:
a user's own key is preferred, but its absence silently falls back to the shared,
rate-limited global app key so brand-new users get a zero-setup experience.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ..exceptions import AuthenticationError
from ..providers.base import ModelProvider
from ..quota.tenant import TenantContext
from ..types import ModelTier

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

        Keys are looked up in the tenant's metadata under ``user_key:<family>``
        and ``tenant_key:<family>`` (where ``<family>`` is the provider name
        prefix, e.g. ``openai``). A ``FREE`` tier provider is keyless. A zero-setup
        tenant with no key of its own rides the shared, rate-limited global app
        key. Anything else is unauthenticated.

        Raises:
            AuthenticationError: If no credential of any tier can be resolved and
                the provider is not keyless.
        """
        family = provider.name.split(":", 1)[0]

        user_key = tenant.metadata.get(f"user_key:{family}")
        if user_key:
            return Credential(
                provider_name=provider.name,
                source=CredentialSource.USER,
                secret_ref=_mask(user_key),
            )

        tenant_key = tenant.metadata.get(f"tenant_key:{family}")
        if tenant_key:
            return Credential(
                provider_name=provider.name,
                source=CredentialSource.TENANT,
                secret_ref=_mask(tenant_key),
            )

        if provider.tier is ModelTier.FREE:
            return Credential(
                provider_name=provider.name,
                source=CredentialSource.FREE_TIER,
                secret_ref="keyless",
            )

        if tenant.is_zero_setup:
            return Credential(
                provider_name=provider.name,
                source=CredentialSource.GLOBAL_APP,
                secret_ref="global-app-key",
                is_rate_limited=True,
            )

        raise AuthenticationError(
            f"no credential available for provider {provider.name!r}"
        )


def _mask(secret: str) -> str:
    """Return a non-reversible reference to a secret for safe storage/logging."""
    if len(secret) <= 4:
        return "****"
    return f"****{secret[-4:]}"
