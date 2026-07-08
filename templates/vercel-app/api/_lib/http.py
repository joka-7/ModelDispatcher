"""Pure request/response (de)serialization helpers for the gateway wrapper.

No web framework and no gateway wiring live here — just the mapping between the
JSON envelope the frontend speaks and the library's typed DTOs. Keeping this
framework-free means the same helpers back the Vercel handler and the unit tests.
"""

from __future__ import annotations

from typing import Any

from model_dispatcher import CompletionRequest, Message, Role, TenantId
from model_dispatcher.orchestration.result import RunResult

#: Fallback tenant id when the request omits one (zero-setup shared capacity).
DEFAULT_TENANT_ID = "anonymous"


def parse_dispatch_request(payload: dict[str, Any]) -> tuple[CompletionRequest, str]:
    """Validate a raw JSON body into a :class:`CompletionRequest` + tenant id.

    Args:
        payload: The decoded JSON object from the request body.

    Returns:
        The typed completion request and the resolved tenant id.

    Raises:
        ValueError: If ``prompt`` is missing or not a non-empty string.
    """
    prompt = payload.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("field 'prompt' must be a non-empty string")

    tenant_id = payload.get("tenant_id")
    resolved = (
        tenant_id if isinstance(tenant_id, str) and tenant_id else DEFAULT_TENANT_ID
    )

    request = CompletionRequest(
        messages=(Message(role=Role.USER, content=prompt),),
        tenant=TenantId(resolved),
    )
    return request, resolved


def serialise_result(result: RunResult, complexity: str) -> dict[str, Any]:
    """Render a :class:`RunResult` into the JSON shape the TS client expects.

    Mirrors ``GatewayResult`` in the TypeScript client and the demo backend, so
    the two stay wire-compatible — including ``complexity``, which the gateway
    itself doesn't return on :class:`RunResult` (routing consumes it internally
    and moves on), so the caller must classify separately and pass it in here.

    Args:
        result: The completed dispatch to serialise.
        complexity: The :class:`~model_dispatcher.types.TaskComplexity` name the
            request was triaged to, e.g. ``"TRIVIAL"``.
    """
    return {
        "final": result.final_message.content,
        "stop_reason": result.stop_reason.value,
        "complexity": complexity,
        "usage": {
            "prompt": result.usage.prompt_tokens,
            "completion": result.usage.completion_tokens,
            "total": result.usage.total_tokens,
        },
        "steps": [
            {
                "message": step.message.content,
                "usage": step.usage.total_tokens,
                "attempts": [
                    {
                        "provider": attempt.provider_name,
                        "error": (
                            attempt.error_class.value if attempt.error_class else None
                        ),
                    }
                    for attempt in step.attempts
                ],
            }
            for step in result.steps
        ],
    }
