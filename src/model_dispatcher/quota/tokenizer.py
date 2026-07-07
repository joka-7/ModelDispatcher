"""Pre-flight token estimation.

Quota reservation happens *before* a model call, so it needs a cheap, provider-
agnostic estimate of how many tokens a request will consume. The estimate is
intentionally conservative (rounds up) so reservations never under-count and let
a tenant slip past their cap.
"""

from __future__ import annotations

import json
import math

from ..types import CompletionRequest

__all__ = ["TokenCounter"]

# Fixed per-message envelope cost (role markers, delimiters) in tokens.
_MESSAGE_OVERHEAD = 4


class TokenCounter:
    """Heuristic, provider-agnostic token estimator.

    Algorithm:
        Absent a provider-specific tokenizer, tokens are approximated from
        character length using a configurable ``chars_per_token`` ratio (≈4 for
        English), summed across every message and tool schema in the request,
        plus a fixed per-message overhead for role/formatting envelope tokens.
        The result is rounded up. Concrete providers may override with an exact
        tokenizer (e.g. ``tiktoken``) when available.
    """

    def __init__(self, chars_per_token: float = 4.0) -> None:
        """Initialise with the average character-to-token ratio to assume."""
        if chars_per_token <= 0:
            raise ValueError("chars_per_token must be positive")
        self._chars_per_token = chars_per_token

    def estimate(self, request: CompletionRequest) -> int:
        """Return a conservative prompt-token estimate for ``request``."""
        chars = 0
        for message in request.messages:
            if message.content:
                chars += len(message.content)
            for call in message.tool_calls:
                chars += len(call.name) + len(json.dumps(call.arguments))
            if message.tool_result is not None:
                chars += len(message.tool_result.content)

        tool_chars = sum(
            len(tool.name) + len(tool.description) + len(json.dumps(tool.parameters))
            for tool in request.tools
        )

        overhead = _MESSAGE_OVERHEAD * len(request.messages)
        estimated = (chars + tool_chars) / self._chars_per_token + overhead
        return math.ceil(estimated)
