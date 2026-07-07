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

import time

from ..fallback.chain import FallbackChain
from ..fallback.handlers import InvocationContext
from ..providers.base import ModelProvider
from ..quota.tenant import TenantContext
from ..types import CompletionResponse, Message, Role
from .result import RunResult, StepResult, StopReason
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
        tenant: TenantContext,
        tools: ToolRegistry,
        chain: FallbackChain,
        candidates: list[ModelProvider],
        *,
        deadline: float | None = None,
    ) -> RunResult:
        """Execute the loop synchronously and return the terminal result.

        Algorithm:
            Repeat up to ``max_iterations`` times:

                1. If ``deadline`` has passed, stop with ``DEADLINE``.
                2. Snapshot ``state`` into a request and dispatch it through the
                   fallback ``chain`` (fresh candidate copy per turn).
                3. Append the assistant message; fold in token usage.
                4. If the message contains tool calls, execute each via
                   ``ToolExecutor``, append the results as messages, and loop.
                5. Otherwise the model answered — stop with ``COMPLETED``.

            If the iteration cap is hit first, stop with ``MAX_ITERATIONS``.
        """
        executor = ToolExecutor(tools)
        steps: list[StepResult] = []

        for _ in range(self._max_iterations):
            if self._past_deadline(deadline):
                return self._finalize(state, steps, StopReason.DEADLINE)

            context = self._dispatch_turn(state, tenant, chain, candidates)
            message = self._absorb(state, steps, context)

            if message.tool_calls:
                self._run_tool_calls(state, executor, message)
                continue
            return self._finalize(state, steps, StopReason.COMPLETED)

        return self._finalize(state, steps, StopReason.MAX_ITERATIONS)

    async def arun(
        self,
        state: ConversationState,
        tenant: TenantContext,
        tools: ToolRegistry,
        chain: FallbackChain,
        candidates: list[ModelProvider],
        *,
        deadline: float | None = None,
    ) -> RunResult:
        """Async counterpart of :meth:`run`."""
        executor = ToolExecutor(tools)
        steps: list[StepResult] = []

        for _ in range(self._max_iterations):
            if self._past_deadline(deadline):
                return self._finalize(state, steps, StopReason.DEADLINE)

            context = InvocationContext(
                request=state.to_request(),
                tenant=tenant,
                candidates=list(candidates),
            )
            response = await chain.aexecute(context)
            message = self._absorb_response(state, steps, context, response)
            context.response = response

            if message.tool_calls:
                await self._arun_tool_calls(state, executor, message)
                continue
            return self._finalize(state, steps, StopReason.COMPLETED)

        return self._finalize(state, steps, StopReason.MAX_ITERATIONS)

    # -- helpers ---------------------------------------------------------- #

    def _dispatch_turn(
        self,
        state: ConversationState,
        tenant: TenantContext,
        chain: FallbackChain,
        candidates: list[ModelProvider],
    ) -> InvocationContext:
        """Build the per-turn context and run it through the chain (helper)."""
        context = InvocationContext(
            request=state.to_request(),
            tenant=tenant,
            candidates=list(candidates),
        )
        response = chain.execute(context)
        context.response = response
        return context

    def _absorb(
        self,
        state: ConversationState,
        steps: list[StepResult],
        context: InvocationContext,
    ) -> Message:
        """Fold a completed turn's context into state and step history."""
        assert context.response is not None  # noqa: S101 - set by _dispatch_turn
        return self._absorb_response(state, steps, context, context.response)

    @staticmethod
    def _absorb_response(
        state: ConversationState,
        steps: list[StepResult],
        context: InvocationContext,
        response: CompletionResponse,
    ) -> Message:
        """Record the assistant message, usage, and attempt trail for a turn."""
        state.append(response.message)
        state.add_usage(response.usage)
        state.iterations += 1
        steps.append(
            StepResult(
                message=response.message,
                usage=response.usage,
                attempts=tuple(context.attempts),
            )
        )
        return response.message

    def _run_tool_calls(
        self, state: ConversationState, executor: ToolExecutor, message: Message
    ) -> None:
        """Execute the message's tool calls and append their results."""
        for call in message.tool_calls:
            result = executor.execute(call)
            state.append(Message(role=Role.TOOL, tool_result=result))

    async def _arun_tool_calls(
        self, state: ConversationState, executor: ToolExecutor, message: Message
    ) -> None:
        """Async counterpart of :meth:`_run_tool_calls`."""
        for call in message.tool_calls:
            result = await executor.aexecute(call)
            state.append(Message(role=Role.TOOL, tool_result=result))

    @staticmethod
    def _past_deadline(deadline: float | None) -> bool:
        """Return whether the monotonic ``deadline`` has elapsed."""
        return deadline is not None and time.monotonic() > deadline

    @staticmethod
    def _finalize(
        state: ConversationState,
        steps: list[StepResult],
        reason: StopReason,
    ) -> RunResult:
        """Assemble the terminal :class:`RunResult` from accumulated state."""
        final = next(
            (m for m in reversed(state.messages) if m.role is Role.ASSISTANT),
            Message(role=Role.ASSISTANT, content=""),
        )
        return RunResult(
            final_message=final,
            transcript=tuple(state.messages),
            usage=state.usage,
            stop_reason=reason,
            steps=tuple(steps),
        )
