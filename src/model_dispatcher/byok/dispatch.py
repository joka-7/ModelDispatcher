"""Timeout-bounded dispatch for a server serving live visitor requests.

No built-in provider adapter sets a network timeout on the vendor client it
constructs (checked directly against each adapter's source -- none exposes a
``timeout`` knob), so a stuck connection or a slow vendor API can otherwise
hang for as long as that vendor SDK's own default allows. A live server needs
a hard ceiling regardless of what the library does internally -- these wrap
:meth:`~model_dispatcher.gateway.ModelGateway.dispatch` /
:meth:`~model_dispatcher.gateway.ModelGateway.adispatch` in that ceiling so
each consumer doesn't have to build its own.
"""

from __future__ import annotations

import asyncio
import concurrent.futures

from ..exceptions import DispatchTimeoutError
from ..gateway import ModelGateway
from ..orchestration.result import RunResult
from ..orchestration.tools import ToolRegistry
from ..quota.tenant import TenantContext
from ..types import CompletionRequest

__all__ = ["dispatch_with_timeout", "adispatch_with_timeout"]


def dispatch_with_timeout(
    gateway: ModelGateway,
    request: CompletionRequest,
    tenant: TenantContext,
    *,
    executor: concurrent.futures.ThreadPoolExecutor,
    timeout_seconds: float,
    tools: ToolRegistry | None = None,
) -> RunResult:
    """Run ``gateway.dispatch`` on ``executor``, bounded by ``timeout_seconds``.

    ``executor`` is the caller's own -- own its lifecycle (create once at
    startup, shut down on exit) the same way a gateway itself is built once.

    Raises:
        DispatchTimeoutError: If dispatch does not finish in time. The
            worker thread keeps running in the background until the
            underlying socket itself errors or completes; this bounds the
            *caller's* wait, not the provider call itself.
    """
    future = executor.submit(gateway.dispatch, request, tenant, tools=tools)
    try:
        return future.result(timeout=timeout_seconds)
    except concurrent.futures.TimeoutError:
        raise DispatchTimeoutError(
            f"dispatch did not complete within {timeout_seconds:.0f}s"
        ) from None


async def adispatch_with_timeout(
    gateway: ModelGateway,
    request: CompletionRequest,
    tenant: TenantContext,
    *,
    timeout_seconds: float,
    tools: ToolRegistry | None = None,
) -> RunResult:
    """Async counterpart of :func:`dispatch_with_timeout`.

    No executor to inject: :func:`asyncio.wait_for` cancels the awaited
    coroutine itself on timeout rather than needing a dedicated thread.

    Raises:
        DispatchTimeoutError: If dispatch does not finish in time.
    """
    try:
        return await asyncio.wait_for(
            gateway.adispatch(request, tenant, tools=tools), timeout=timeout_seconds
        )
    except TimeoutError:
        raise DispatchTimeoutError(
            f"dispatch did not complete within {timeout_seconds:.0f}s"
        ) from None
