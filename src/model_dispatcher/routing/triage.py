"""Task triage: classify how much reasoning a request demands.

Triage is the first half of cost routing. It inspects a request *before* any
model is called and assigns a :class:`TaskComplexity`, which the router then maps
onto a minimum tier. The classifier is deliberately cheap and deterministic (no
model call) and is pluggable via a strategy callable for teams that want a
learned classifier later.
"""

from __future__ import annotations

from collections.abc import Callable

from ..types import CompletionRequest, TaskComplexity

__all__ = ["ComplexityScorer", "TaskTriage"]

type ComplexityScorer = Callable[[CompletionRequest], TaskComplexity]
"""Pluggable strategy mapping a request to a complexity verdict."""


class TaskTriage:
    """Heuristic complexity classifier.

    Algorithm:
        A weighted score is accumulated from cheap, observable signals and then
        bucketed into a :class:`TaskComplexity`:

        1. **Input size** — longer prompts (more tokens/messages) raise the score.
        2. **Tool surface** — the presence and count of declared tools implies an
           agentic, multi-step task and raises the score.
        3. **Reasoning signals** — keyword/marker heuristics (e.g. "prove",
           "step by step", code fences, nested questions) raise the score.
        4. **Requested output size** — large ``max_tokens`` implies heavier work.

        The summed score is mapped through fixed thresholds onto ``TRIVIAL`` ..
        ``COMPLEX``. A caller-supplied ``tier_hint`` on the request can only
        *raise* the floor, never lower it below the heuristic verdict.
    """

    def __init__(self, scorer: ComplexityScorer | None = None) -> None:
        """Initialise with an optional custom scorer (defaults to the heuristic)."""
        self._scorer = scorer

    def classify(self, request: CompletionRequest) -> TaskComplexity:
        """Return the complexity verdict for ``request``."""
        raise NotImplementedError
