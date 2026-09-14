"""Behavioral tests for the `byok` server-integration subpackage."""

from __future__ import annotations

import asyncio
import concurrent.futures
import time
from collections.abc import Callable

import pytest

from model_dispatcher import (
    CompletionRequest,
    CompletionResponse,
    ErrorClass,
    Message,
    ModelGateway,
    ModelProvider,
    ModelTier,
    ProviderCapability,
    ProviderRegistry,
    Role,
    TenantContext,
)
from model_dispatcher.byok import (
    ProviderSpec,
    adispatch_with_timeout,
    build_registry,
    configured_providers,
    credential_metadata,
    dispatch_with_timeout,
)
from model_dispatcher.exceptions import DispatchTimeoutError, NoProviderAvailableError
from model_dispatcher.providers import MockProvider


def _mock_factory(*, model: str, api_key: str | None = None) -> ModelProvider:
    """Stand in for a real provider class: MockProvider takes no `api_key`."""
    return MockProvider(name=f"mock:{model}")


class _SlowProvider(ModelProvider):
    """A provider whose calls sleep well past any test's timeout."""

    def __init__(self, delay_seconds: float) -> None:
        self.name = "slow:test"
        self.tier = ModelTier.FREE
        self.capabilities = ProviderCapability.TOOLS
        self._delay_seconds = delay_seconds

    def complete(
        self, request: CompletionRequest, *, api_key: str | None = None
    ) -> CompletionResponse:
        time.sleep(self._delay_seconds)
        raise AssertionError("should have timed out before returning")

    async def acomplete(
        self, request: CompletionRequest, *, api_key: str | None = None
    ) -> CompletionResponse:
        await asyncio.sleep(self._delay_seconds)
        raise AssertionError("should have timed out before returning")

    def estimate_tokens(self, request: CompletionRequest) -> int:
        return 1

    def classify_error(self, exc: Exception) -> ErrorClass:
        return ErrorClass.TRANSIENT


_SPECS = {
    "gemini": ProviderSpec(
        _mock_factory, "GEMINI_API_KEY", "GEMINI_MODEL", "gemini-default"
    ),
    "openai": ProviderSpec(
        _mock_factory, "OPENAI_API_KEY", "OPENAI_MODEL", "openai-default"
    ),
}


class TestBuildRegistry:
    def test_registers_a_vendor_with_a_server_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "server-key")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        registry = build_registry(_SPECS, {})

        assert len(registry) == 1
        assert registry.get("mock:gemini-default")

    def test_registers_a_vendor_with_only_a_visitor_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        registry = build_registry(_SPECS, {"gemini": ["visitor-key"]})

        assert len(registry) == 1
        assert registry.get("mock:gemini-default")

    def test_model_env_var_overrides_the_default_model(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "server-key")
        monkeypatch.setenv("GEMINI_MODEL", "gemini-custom")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        registry = build_registry(_SPECS, {})

        assert registry.get("mock:gemini-custom")

    def test_excludes_a_vendor_with_neither_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "server-key")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        registry = build_registry(_SPECS, {})

        assert "mock:openai-default" not in registry

    def test_raises_when_no_vendor_has_any_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        with pytest.raises(NoProviderAvailableError):
            build_registry(_SPECS, {})


class TestCredentialMetadata:
    def test_joins_multiple_keys_per_vendor_with_commas(self) -> None:
        result = credential_metadata({"openai": ["sk-aaa", "sk-bbb"]})
        assert result == {"user_key:openai": "sk-aaa,sk-bbb"}

    def test_omits_vendors_with_no_keys(self) -> None:
        assert credential_metadata({"openai": []}) == {}

    def test_empty_input_yields_empty_metadata(self) -> None:
        assert credential_metadata({}) == {}


class TestConfiguredProviders:
    def test_reports_only_vendors_with_a_server_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "server-key")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        assert configured_providers(_SPECS) == frozenset({"gemini"})


class TestDispatchWithTimeout:
    def _request(self, tenant: TenantContext) -> CompletionRequest:
        return CompletionRequest(
            messages=(Message(role=Role.USER, content="hello"),),
            tenant=tenant.tenant_id,
        )

    def test_returns_the_result_within_budget(
        self,
        make_gateway: Callable[..., ModelGateway],
        make_tenant: Callable[..., TenantContext],
    ) -> None:
        gateway = make_gateway(MockProvider("mock:free", reply="hi!"))
        tenant = make_tenant()
        request = self._request(tenant)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            result = dispatch_with_timeout(
                gateway, request, tenant, executor=executor, timeout_seconds=5.0
            )
        assert result.final_message.content == "hi!"

    def test_raises_on_timeout(
        self,
        make_tenant: Callable[..., TenantContext],
    ) -> None:
        registry = ProviderRegistry()
        registry.register(_SlowProvider(delay_seconds=0.2))
        gateway = ModelGateway.create(registry)
        tenant = make_tenant()

        request = self._request(tenant)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            with pytest.raises(DispatchTimeoutError):
                dispatch_with_timeout(
                    gateway, request, tenant, executor=executor, timeout_seconds=0.02
                )


class TestAdispatchWithTimeout:
    def _request(self, tenant: TenantContext) -> CompletionRequest:
        return CompletionRequest(
            messages=(Message(role=Role.USER, content="hello"),),
            tenant=tenant.tenant_id,
        )

    async def test_returns_the_result_within_budget(
        self,
        make_gateway: Callable[..., ModelGateway],
        make_tenant: Callable[..., TenantContext],
    ) -> None:
        gateway = make_gateway(MockProvider("mock:free", reply="hi!"))
        tenant = make_tenant()
        result = await adispatch_with_timeout(
            gateway, self._request(tenant), tenant, timeout_seconds=5.0
        )
        assert result.final_message.content == "hi!"

    async def test_raises_on_timeout(
        self,
        make_tenant: Callable[..., TenantContext],
    ) -> None:
        registry = ProviderRegistry()
        registry.register(_SlowProvider(delay_seconds=0.2))
        gateway = ModelGateway.create(registry)
        tenant = make_tenant()

        with pytest.raises(DispatchTimeoutError):
            await adispatch_with_timeout(
                gateway, self._request(tenant), tenant, timeout_seconds=0.02
            )
