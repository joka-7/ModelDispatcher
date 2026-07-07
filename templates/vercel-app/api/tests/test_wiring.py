"""Tests for per-tier live-vs-mock provider selection in `_lib.wiring`."""

from __future__ import annotations

import pytest
from _lib.wiring import build_gateway

from model_dispatcher.providers import AnthropicProvider, MockProvider, OpenAIProvider


def test_all_mock_when_no_keys_are_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """With no vendor keys set, every tier falls back to a keyless mock."""
    for var in ("MD_OPENAI_API_KEY", "MD_ANTHROPIC_API_KEY", "MD_GEMINI_API_KEY"):
        monkeypatch.delenv(var, raising=False)

    gateway = build_gateway()

    providers = gateway.providers.all()
    assert len(providers) == 3
    assert all(isinstance(p, MockProvider) for p in providers)


def test_a_single_configured_key_upgrades_only_that_tier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Setting one provider's key swaps in the real adapter for its tier only."""
    monkeypatch.setenv("MD_OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("MD_ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("MD_GEMINI_API_KEY", raising=False)

    gateway = build_gateway()

    providers = gateway.providers.all()
    openai = [p for p in providers if isinstance(p, OpenAIProvider)]
    mocks = [p for p in providers if isinstance(p, MockProvider)]
    assert len(openai) == 1
    assert len(mocks) == 2
    assert openai[0].name == "openai:gpt-4o-mini"


def test_model_env_override_is_honoured(monkeypatch: pytest.MonkeyPatch) -> None:
    """A *_MODEL env var overrides the default model id for that tier."""
    monkeypatch.setenv("MD_ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("MD_ANTHROPIC_MODEL", "claude-haiku-4-5")
    monkeypatch.delenv("MD_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("MD_GEMINI_API_KEY", raising=False)

    gateway = build_gateway()

    anthropic = [p for p in gateway.providers.all() if isinstance(p, AnthropicProvider)]
    assert len(anthropic) == 1
    assert anthropic[0].name == "anthropic:claude-haiku-4-5"
