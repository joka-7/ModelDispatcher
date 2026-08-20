"""Internal helpers for offering sync and async APIs from one core.

Both the synchronous and asynchronous public APIs are first-class. Rather than
duplicating pipeline logic, the sync entry points delegate to the async core
through :func:`run_sync`, which safely drives a coroutine to completion from a
synchronous caller. This module is private; callers use :class:`ModelGateway`.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Coroutine
from typing import TypeVar

__all__ = ["run_sync"]

_T = TypeVar("_T")


def run_sync(coro: Coroutine[object, object, _T]) -> _T:
    """Drive ``coro`` to completion from synchronous code and return its result.

    Algorithm:
        If no event loop is running in the current thread, use
        :func:`asyncio.run`. If a loop *is* already running (e.g. the sync API
        was called from within async code), execute the coroutine on a dedicated
        worker thread with its own loop to avoid re-entrancy deadlocks.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result: list[_T] = []
    error: list[BaseException] = []

    def _worker() -> None:
        try:
            result.append(asyncio.run(coro))
        except BaseException as exc:  # noqa: BLE001 - re-raised on the caller thread
            error.append(exc)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    thread.join()

    if error:
        raise error[0]
    return result[0]
