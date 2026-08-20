"""Tool registration and execution for the agent loop.

Tools are plain Python callables paired with a JSON-Schema :class:`ToolSpec`. The
registry advertises their specs to the model; the executor dispatches a decoded
:class:`ToolCall` to the matching callable and captures the result (or error) as
a :class:`ToolResult` to feed back into the conversation.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeAlias

from ..types import JSONValue, ToolCall, ToolResult, ToolSpec

__all__ = ["ToolHandler", "AsyncToolHandler", "Tool", "ToolRegistry", "ToolExecutor"]

ToolHandler: TypeAlias = Callable[[dict[str, JSONValue]], str]
"""Synchronous tool implementation: decoded arguments in, string content out."""

AsyncToolHandler: TypeAlias = Callable[[dict[str, JSONValue]], Awaitable[str]]
"""Asynchronous tool implementation."""


@dataclass(frozen=True, slots=True)
class Tool:
    """A callable tool bound to its schema.

    Exactly one of ``handler``/``ahandler`` is used depending on whether the loop
    is driven synchronously or asynchronously.
    """

    spec: ToolSpec
    handler: ToolHandler | None = None
    ahandler: AsyncToolHandler | None = None


class ToolRegistry:
    """Name-indexed collection of tools available to a run."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Add ``tool``, replacing any existing tool of the same name."""
        self._tools[tool.spec.name] = tool

    def specs(self) -> tuple[ToolSpec, ...]:
        """Return the specs advertised to the model, in registration order."""
        return tuple(tool.spec for tool in self._tools.values())

    def get(self, name: str) -> Tool:
        """Return the tool registered under ``name``.

        Raises:
            KeyError: If no tool is registered under that name.
        """
        return self._tools[name]

    def __contains__(self, name: object) -> bool:
        """Return whether a tool is registered under ``name``."""
        return name in self._tools


class ToolExecutor:
    """Dispatches decoded tool calls to their registered implementations."""

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    def execute(self, call: ToolCall) -> ToolResult:
        """Run ``call`` synchronously and capture its outcome.

        A raised handler exception is caught and returned as a
        :class:`ToolResult` with ``is_error=True`` so the loop can feed the error
        back to the model rather than aborting the whole run.
        """
        try:
            tool = self._registry.get(call.name)
        except KeyError:
            return ToolResult(call.id, f"unknown tool: {call.name}", is_error=True)
        if tool.handler is None:
            return ToolResult(
                call.id, f"tool {call.name} has no synchronous handler", is_error=True
            )
        try:
            content = tool.handler(call.arguments)
        except Exception as exc:  # noqa: BLE001 - surfaced back to the model
            return ToolResult(call.id, f"tool error: {exc}", is_error=True)
        return ToolResult(call.id, content)

    async def aexecute(self, call: ToolCall) -> ToolResult:
        """Async counterpart of :meth:`execute`."""
        try:
            tool = self._registry.get(call.name)
        except KeyError:
            return ToolResult(call.id, f"unknown tool: {call.name}", is_error=True)
        try:
            if tool.ahandler is not None:
                content = await tool.ahandler(call.arguments)
            elif tool.handler is not None:
                content = tool.handler(call.arguments)
            else:
                return ToolResult(
                    call.id, f"tool {call.name} has no handler", is_error=True
                )
        except Exception as exc:  # noqa: BLE001 - surfaced back to the model
            return ToolResult(call.id, f"tool error: {exc}", is_error=True)
        return ToolResult(call.id, content)
