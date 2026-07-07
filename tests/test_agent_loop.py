"""Contract tests for orchestration value types and loop wiring."""

from __future__ import annotations

from model_dispatcher.orchestration import (
    AgentLoop,
    ConversationState,
    RunResult,
    StopReason,
)
from model_dispatcher.types import Message, Role, TenantId, Usage


def test_conversation_state_starts_empty() -> None:
    state = ConversationState(
        tenant=TenantId("t1"),
        messages=[Message(role=Role.USER, content="hi")],
    )
    assert state.iterations == 0
    assert state.usage.total_tokens == 0
    assert len(state.messages) == 1


def test_stop_reasons_are_exhaustive() -> None:
    assert {r.value for r in StopReason} == {
        "completed",
        "max_iterations",
        "deadline",
        "error",
    }


def test_run_result_is_constructible() -> None:
    msg = Message(role=Role.ASSISTANT, content="done")
    result = RunResult(
        final_message=msg,
        transcript=(msg,),
        usage=Usage(),
        stop_reason=StopReason.COMPLETED,
    )
    assert result.final_message is msg
    assert result.stop_reason is StopReason.COMPLETED


def test_agent_loop_accepts_iteration_ceiling() -> None:
    loop = AgentLoop(max_iterations=8)
    assert isinstance(loop, AgentLoop)
