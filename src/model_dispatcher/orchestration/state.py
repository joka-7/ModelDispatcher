"""Mutable conversation state for one agent run.

The agent loop is intentionally stateless; all evolving data lives here. Keeping
state in one explicit, inspectable object (rather than hidden inside a framework)
is the point of the "native orchestration" requirement — it makes the loop
trivial to test, checkpoint, and reason about.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..types import (
    CompletionRequest,
    Message,
    TenantId,
    ToolSpec,
    Usage,
)

__all__ = ["ConversationState"]


@dataclass(slots=True)
class ConversationState:
    """Evolving history, usage, and counters for a single run.

    Attributes:
        tenant: Owning tenant, propagated onto every derived request.
        messages: Full ordered transcript, appended to as the loop turns.
        tools: Tool specifications advertised to the model each turn.
        usage: Cumulative token usage across all turns so far.
        iterations: Number of model turns executed so far.
    """

    tenant: TenantId
    messages: list[Message]
    tools: tuple[ToolSpec, ...] = ()
    usage: Usage = field(default_factory=Usage)
    iterations: int = 0

    def append(self, message: Message) -> None:
        """Append a message to the transcript (assistant, tool result, ...)."""
        self.messages.append(message)

    def add_usage(self, usage: Usage) -> None:
        """Fold a turn's token usage into the running total."""
        self.usage = self.usage + usage

    def to_request(self) -> CompletionRequest:
        """Snapshot the current state into an immutable completion request.

        This is what the loop feeds to the fallback chain each turn, so the model
        always sees the full, up-to-date transcript including prior tool results.
        """
        return CompletionRequest(
            messages=tuple(self.messages),
            tenant=self.tenant,
            tools=self.tools,
        )
