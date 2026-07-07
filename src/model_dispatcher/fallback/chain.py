"""Builder and executor for the fallback chain of responsibility.

The chain owns the control flow that makes provider failover transparent: it
walks the ordered handlers, and when one returns ``FALLBACK`` it drops the
current candidate and restarts from the top with the next provider — until a
response is produced or the candidate list is exhausted.
"""

from __future__ import annotations

from collections.abc import Sequence

from ..exceptions import AllProvidersExhausted, ModelDispatcherError
from ..types import CompletionResponse
from .handlers import FallbackHandler, HandlerOutcome, InvocationContext

__all__ = ["FallbackChain"]


class FallbackChain:
    """A composed, executable chain of :class:`FallbackHandler` links."""

    def __init__(self, handlers: Sequence[FallbackHandler]) -> None:
        self._handlers: tuple[FallbackHandler, ...] = tuple(handlers)

    @classmethod
    def build(cls, handlers: Sequence[FallbackHandler]) -> FallbackChain:
        """Link ``handlers`` head-to-tail and return the runnable chain.

        Raises:
            ValueError: If ``handlers`` is empty.
        """
        handlers = list(handlers)
        if not handlers:
            raise ValueError("a fallback chain needs at least one handler")
        for current, nxt in zip(handlers, handlers[1:], strict=False):
            current.set_next(nxt)
        return cls(handlers)

    def execute(self, context: InvocationContext) -> CompletionResponse:
        """Run the chain synchronously and return the winning response.

        Algorithm:
            Loop over the handler list from the head. Interpret each
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
        self._require_candidates(context)
        while True:
            outcome = HandlerOutcome.CONTINUE
            for handler in self._handlers:
                outcome = handler.handle(context)
                if outcome is HandlerOutcome.SUCCESS:
                    return self._succeed(context)
                if outcome is HandlerOutcome.STOP:
                    raise self._stop_error(context)
                if outcome is HandlerOutcome.FALLBACK:
                    break
            self._advance_or_raise(context, outcome)

    async def aexecute(self, context: InvocationContext) -> CompletionResponse:
        """Async counterpart of :meth:`execute`."""
        self._require_candidates(context)
        while True:
            outcome = HandlerOutcome.CONTINUE
            for handler in self._handlers:
                outcome = await handler.ahandle(context)
                if outcome is HandlerOutcome.SUCCESS:
                    return self._succeed(context)
                if outcome is HandlerOutcome.STOP:
                    raise self._stop_error(context)
                if outcome is HandlerOutcome.FALLBACK:
                    break
            self._advance_or_raise(context, outcome)

    @staticmethod
    def _require_candidates(context: InvocationContext) -> None:
        """Raise immediately if the router produced no candidates."""
        if not context.candidates:
            raise AllProvidersExhausted("no candidate providers were routed")

    @staticmethod
    def _succeed(context: InvocationContext) -> CompletionResponse:
        """Return the response recorded by the invocation handler."""
        assert context.response is not None  # noqa: S101 - guaranteed by SUCCESS
        return context.response

    @staticmethod
    def _stop_error(context: InvocationContext) -> Exception:
        """Return the exception a ``STOP`` outcome should raise."""
        return context.error or ModelDispatcherError("fallback chain stopped")

    @staticmethod
    def _advance_or_raise(context: InvocationContext, outcome: HandlerOutcome) -> None:
        """Consume the current candidate on ``FALLBACK`` or fail the chain."""
        if outcome is not HandlerOutcome.FALLBACK:
            # Every handler returned CONTINUE without a terminal outcome; this is
            # a composition error (no invocation handler produced a response).
            raise AllProvidersExhausted("fallback chain produced no response")
        context.candidates.pop(0)
        context.reset_candidate_state()
        if not context.candidates:
            raise AllProvidersExhausted("all routed providers were exhausted")
