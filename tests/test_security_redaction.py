"""Behavioral tests for credential resolution and secret redaction."""

from __future__ import annotations

from model_dispatcher import ModelTier, TenantContext, TenantId, TenantQuota
from model_dispatcher.providers import MockProvider
from model_dispatcher.security.credentials import CredentialResolver, CredentialSource
from model_dispatcher.security.redaction import SecretRedactor


def _tenant(**metadata: str) -> TenantContext:
    return TenantContext(
        tenant_id=TenantId("t"),
        quota=TenantQuota(requests_per_min=1, tokens_per_min=1, tokens_per_day=1),
        metadata=metadata,
    )


def test_redactor_scrubs_sensitive_keys_and_values() -> None:
    redactor = SecretRedactor()
    scrubbed = redactor.scrub(
        {
            "api_key": "sk-verysecretkey1234567890",
            "nested": {"authorization": "Bearer abc"},
            "safe": "plain text",
        }
    )
    assert scrubbed == {
        "api_key": "[REDACTED]",
        "nested": {"authorization": "[REDACTED]"},
        "safe": "plain text",
    }


def test_redactor_scrubs_inline_secret_shaped_text() -> None:
    redactor = SecretRedactor()
    assert "[REDACTED]" in redactor.scrub_text("token is sk-ABCDEFGHIJKLMNOPQRST")


def test_credential_precedence_prefers_user_key() -> None:
    resolver = CredentialResolver()
    provider = MockProvider("openai:gpt", tier=ModelTier.STANDARD)
    credential = resolver.resolve(
        _tenant(**{"user_key:openai": "sk-user-1234"}), provider
    )
    assert credential.source is CredentialSource.USER
    assert credential.secret_ref == "****1234"  # masked, never the raw key


def test_zero_setup_tenant_falls_back_to_global_key() -> None:
    resolver = CredentialResolver()
    provider = MockProvider("openai:gpt", tier=ModelTier.STANDARD)
    credential = resolver.resolve(_tenant(), provider)
    assert credential.source is CredentialSource.GLOBAL_APP
    assert credential.is_rate_limited is True


def test_free_tier_provider_is_keyless() -> None:
    resolver = CredentialResolver()
    provider = MockProvider("local:free", tier=ModelTier.FREE)
    credential = resolver.resolve(_tenant(), provider)
    assert credential.source is CredentialSource.FREE_TIER


def test_resolve_candidates_splits_a_comma_separated_key_pool() -> None:
    resolver = CredentialResolver()
    provider = MockProvider("openai:gpt", tier=ModelTier.STANDARD)
    candidates = resolver.resolve_candidates(
        _tenant(**{"user_key:openai": "sk-aaaa1111, sk-bbbb2222,sk-cccc3333"}), provider
    )
    assert [c.source for c in candidates] == [CredentialSource.USER] * 3
    assert [c.raw_key for c in candidates] == [
        "sk-aaaa1111",
        "sk-bbbb2222",
        "sk-cccc3333",
    ]
    # Masked refs for logging/audit never expose more than a trailing fragment.
    assert [c.secret_ref for c in candidates] == ["****1111", "****2222", "****3333"]


def test_resolve_candidates_a_single_key_is_a_one_element_list() -> None:
    """A tenant with one key behaves exactly as before the multi-key change."""
    resolver = CredentialResolver()
    provider = MockProvider("openai:gpt", tier=ModelTier.STANDARD)
    candidates = resolver.resolve_candidates(
        _tenant(**{"user_key:openai": "sk-user-1234"}), provider
    )
    assert len(candidates) == 1
    assert candidates[0].raw_key == "sk-user-1234"
    assert candidates == [
        resolver.resolve(_tenant(**{"user_key:openai": "sk-user-1234"}), provider)
    ]


def test_credential_repr_never_leaks_the_raw_key() -> None:
    resolver = CredentialResolver()
    provider = MockProvider("openai:gpt", tier=ModelTier.STANDARD)
    credential = resolver.resolve(
        _tenant(**{"user_key:openai": "sk-topsecret999"}), provider
    )
    assert "sk-topsecret999" not in repr(credential)
    assert credential.raw_key == "sk-topsecret999"  # still reachable by field access
