"""Credential resolution with a strict precedence chain.

The resolver decides *which* API credential(s) a given request should use, and
its precedence order is the mechanical basis of the two-stage onboarding flow:
a user's own key is preferred, but its absence silently falls back to the
shared, rate-limited global app key so brand-new users get a zero-setup
experience.

A tenant may register *more than one* key for a provider family (e.g. several
personal API keys pooled for redundancy) — see :meth:`CredentialResolver.
resolve_candidates`. This is the mechanical basis of same-provider key
rotation in :class:`~model_dispatcher.fallback.handlers.ModelInvocationHandler`:
when the first key is rate-limited or exhausted, the next one is tried before
the fallback chain gives up on the provider entirely and moves to the next
candidate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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
        secret_ref: Opaque, masked reference/handle to the secret, safe to log
            or include in a trace (see :class:`SecretRedactor`) — never the
            raw key.
        raw_key: The actual secret value to send to the vendor, or ``None``
            when the provider needs no override (keyless free tier, or the
            shared global app key — which is simply the provider's own
            statically-configured key, not a per-tenant value). Excluded from
            ``repr()`` so an accidental print/log of a ``Credential`` can
            never leak it; callers that need the real value (only
            :class:`~model_dispatcher.fallback.handlers.ModelInvocationHandler`
            should) read this field explicitly.
        is_rate_limited: ``True`` for the shared global key, whose exhaustion is
            what triggers the Stage-2 handoff.
    """

    provider_name: str
    source: CredentialSource
    secret_ref: str
    raw_key: str | None = field(default=None, repr=False, compare=False)
    is_rate_limited: bool = False


class CredentialResolver:
    """Resolves the credential(s) to use for a tenant/provider pair.

    Precedence (first match wins — the whole match, not one key at a time):
        1. **User key(s)** — the caller's own key(s) for this provider. A
           tenant may register several (see :meth:`resolve_candidates`); all
           of them are tried, in registration order, before falling through.
        2. **Tenant key(s)** — organisation-wide key(s) shared by the tenant.
        3. **Global app key** — the shared, rate-limited application key that
           powers the zero-setup stage.
        4. **Free tier** — a keyless free/local provider as the final safety net.
    """

    def resolve(self, tenant: TenantContext, provider: ModelProvider) -> Credential:
        """Return the single highest-precedence credential for the pair.

        Convenience wrapper over :meth:`resolve_candidates` for callers that
        only need one credential (e.g. onboarding-stage bookkeeping); the
        invocation path that actually calls the provider should prefer
        :meth:`resolve_candidates` so it can rotate through every available
        key before giving up on the provider.

        Raises:
            AuthenticationError: If no credential of any tier can be resolved
                and the provider is not keyless.
        """
        return self.resolve_candidates(tenant, provider)[0]

    def resolve_candidates(
        self, tenant: TenantContext, provider: ModelProvider
    ) -> list[Credential]:
        """Return every usable credential for the pair, in try-order.

        Keys are looked up in the tenant's metadata under ``user_key:<family>``
        and ``tenant_key:<family>`` (where ``<family>`` is the provider name
        prefix, e.g. ``openai``). Either value may hold more than one key,
        comma-separated (``"sk-aaa, sk-bbb"``) — a single key with no comma is
        just a one-element list, so existing single-key setups are unaffected.
        A ``FREE`` tier provider is keyless. A zero-setup tenant with no key of
        its own rides the shared, rate-limited global app key.

        Raises:
            AuthenticationError: If no credential of any tier can be resolved
                and the provider is not keyless.
        """
        family = provider.name.split(":", 1)[0]

        user_keys = _split_keys(tenant.metadata.get(f"user_key:{family}"))
        if user_keys:
            return [
                Credential(
                    provider_name=provider.name,
                    source=CredentialSource.USER,
                    secret_ref=_mask(key),
                    raw_key=key,
                )
                for key in user_keys
            ]

        tenant_keys = _split_keys(tenant.metadata.get(f"tenant_key:{family}"))
        if tenant_keys:
            return [
                Credential(
                    provider_name=provider.name,
                    source=CredentialSource.TENANT,
                    secret_ref=_mask(key),
                    raw_key=key,
                )
                for key in tenant_keys
            ]

        if provider.tier is ModelTier.FREE:
            return [
                Credential(
                    provider_name=provider.name,
                    source=CredentialSource.FREE_TIER,
                    secret_ref="keyless",
                )
            ]

        if tenant.is_zero_setup:
            return [
                Credential(
                    provider_name=provider.name,
                    source=CredentialSource.GLOBAL_APP,
                    secret_ref="global-app-key",
                    is_rate_limited=True,
                )
            ]

        raise AuthenticationError(
            f"no credential available for provider {provider.name!r}"
        )


def _split_keys(raw: str | None) -> list[str]:
    """Split a possibly-multi-key metadata value into individual keys.

    ``None``/empty -> ``[]``. A single key with no comma -> one-element list,
    so existing single-key tenants behave exactly as before.
    """
    if not raw:
        return []
    return [key.strip() for key in raw.split(",") if key.strip()]


def _mask(secret: str) -> str:
    """Return a non-reversible reference to a secret for safe storage/logging."""
    if len(secret) <= 4:
        return "****"
    return f"****{secret[-4:]}"
