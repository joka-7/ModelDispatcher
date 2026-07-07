"""Internal helpers for offering sync and async APIs from one core.

Both the synchronous and asynchronous public APIs are first-class. Rather than
duplicating pipeline logic, the sync entry points delegate to the async core
through :func:`run_sync`, which safely drives a coroutine to completion from a
synchronous caller. This module is private; callers use :class:`ModelGateway`.
"""

from __future__ import annotations

from collections.abc import Coroutine

__all__ = ["run_sync"]


def run_sync[T](coro: Coroutine[object, object, T]) -> T:
    """Drive ``coro`` to completion from synchronous code and return its result.

    Algorithm:
        If no event loop is running in the current thread, use
        :func:`asyncio.run`. If a loop *is* already running (e.g. the sync API
        was called from within async code), execute the coroutine on a dedicated
        worker thread with its own loop to avoid re-entrancy deadlocks.
    """
    raise NotImplementedError
