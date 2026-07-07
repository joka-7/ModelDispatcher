"""Result objects returned by the agent loop."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from ..fallback.handlers import AttemptRecord
from ..types import Message, Usage

__all__ = ["StopReason", "StepResult", "RunResult"]


class StopReason(StrEnum):
    """Why the agent loop terminated."""

    COMPLETED = "completed"
    MAX_ITERATIONS = "max_iterations"
    DEADLINE = "deadline"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class StepResult:
    """Outcome of a single loop iteration (one model turn plus any tool calls).

    Attributes:
        message: The assistant message produced this turn.
        usage: Token usage for this turn.
        attempts: Provider attempts made by the fallback chain this turn.
    """

    message: Message
    usage: Usage
    attempts: tuple[AttemptRecord, ...] = ()


@dataclass(frozen=True, slots=True)
class RunResult:
    """Terminal outcome of a full :class:`AgentLoop` run.

    Attributes:
        final_message: The last assistant message (the answer to the caller).
        transcript: The full ordered message history of the run.
        usage: Cumulative token usage across every turn.
        steps: Per-iteration results, in order.
        stop_reason: Why the loop terminated.
    """

    final_message: Message
    transcript: tuple[Message, ...]
    usage: Usage
    stop_reason: StopReason
    steps: tuple[StepResult, ...] = field(default_factory=tuple)
