"""The native agent execution loop.

This is the orchestration heart of the gateway and the deliberate replacement for
a heavy third-party agent framework. It is a small, explicit loop: send the
conversation to a model (through the fallback chain), and if the model asks for
tools, execute them, append the results, and iterate — otherwise return.

Because *every* model turn goes through the same :class:`FallbackChain`, all the
cross-cutting concerns (security, credentials, quota, rate-limit failover, retry)
apply uniformly on every iteration, including tool-follow-up turns.
"""

from __future__ import annotations

from ..fallback.chain import FallbackChain
from ..fallback.handlers import InvocationContext
from ..providers.base import ModelProvider
from .result import RunResult
from .state import ConversationState
from .tools import ToolExecutor, ToolRegistry

__all__ = ["AgentLoop"]


class AgentLoop:
    """Drives a conversation to completion with tool-calling and fallback.

    The loop holds no per-run state; everything mutable lives in the
    :class:`ConversationState` passed to :meth:`run`/:meth:`arun`.
    """

    def __init__(self, max_iterations: int) -> None:
        """Initialise with a hard ceiling on model turns per run."""
        self._max_iterations = max_iterations

    def run(
        self,
        state: ConversationState,
        tools: ToolRegistry,
        chain: FallbackChain,
        candidates: list[ModelProvider],
        *,
        deadline: float | None = None,
    ) -> RunResult:
        """Execute the loop synchronously and return the terminal result.

        Algorithm:
            Repeat up to ``max_iterations`` times::

                1. If ``deadline`` has passed, stop with ``DEADLINE``.
                2. Snapshot ``state`` into a request and dispatch it through the
                   fallback ``chain`` (fresh candidate list per turn).
                3. Append the assistant message; fold in token usage.
                4. If the message contains tool calls, execute each via
                   ``ToolExecutor``, append the results as messages, and loop.
                5. Otherwise the model answered — stop with ``COMPLETED`` and
                   return the assistant message as ``final_message``.

            If the iteration cap is hit first, stop with ``MAX_ITERATIONS``.

        Args:
            state: Mutable conversation state, updated in place.
            tools: Tools the model may invoke this run.
            chain: The fallback chain each turn is dispatched through.
            candidates: Router-ordered providers seeding each turn's context.
            deadline: Optional monotonic-clock cutoff for the whole run.
        """
        raise NotImplementedError

    async def arun(
        self,
        state: ConversationState,
        tools: ToolRegistry,
        chain: FallbackChain,
        candidates: list[ModelProvider],
        *,
        deadline: float | None = None,
    ) -> RunResult:
        """Async counterpart of :meth:`run`."""
        raise NotImplementedError

    def _dispatch_turn(
        self,
        state: ConversationState,
        chain: FallbackChain,
        candidates: list[ModelProvider],
    ) -> InvocationContext:
        """Build the per-turn context and run it through the chain (helper)."""
        raise NotImplementedError

    def _run_tool_calls(self, state: ConversationState, executor: ToolExecutor) -> None:
        """Execute the pending tool calls on the last message and append results."""
        raise NotImplementedError
