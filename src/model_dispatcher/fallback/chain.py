"""Builder and executor for the fallback chain of responsibility.

The chain owns the control flow that makes provider failover transparent: it
walks the linked handlers, and when one returns ``FALLBACK`` it drops the current
candidate and restarts from the top with the next provider — until a response is
produced or the candidate list is exhausted.
"""

from __future__ import annotations

from collections.abc import Sequence

from ..types import CompletionResponse
from .handlers import FallbackHandler, InvocationContext

__all__ = ["FallbackChain"]


class FallbackChain:
    """A composed, executable chain of :class:`FallbackHandler` links."""

    def __init__(self, head: FallbackHandler) -> None:
        self._head = head

    @classmethod
    def build(cls, handlers: Sequence[FallbackHandler]) -> FallbackChain:
        """Link ``handlers`` head-to-tail and return the runnable chain.

        Raises:
            ValueError: If ``handlers`` is empty.
        """
        raise NotImplementedError

    def execute(self, context: InvocationContext) -> CompletionResponse:
        """Run the chain synchronously and return the winning response.

        Algorithm:
            Loop over the handler list starting at the head. Interpret each
            :class:`HandlerOutcome`:

            * ``CONTINUE`` — advance to the next handler.
            * ``SUCCESS`` — return ``context.response``.
            * ``FALLBACK`` — pop ``context.candidates[0]``; if any remain, restart
              from the head, otherwise raise :class:`AllProvidersExhausted`.
            * ``STOP`` — raise ``context.error`` (perimeter/quota/auth failure).

        Raises:
            AllProvidersExhausted: When every candidate has been consumed.
            ModelDispatcherError: Propagated from a ``STOP`` outcome.
        """
        raise NotImplementedError

    async def aexecute(self, context: InvocationContext) -> CompletionResponse:
        """Async counterpart of :meth:`execute`."""
        raise NotImplementedError
