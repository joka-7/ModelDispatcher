/**
 * Response decoder: HTTP {@link Response} → {@link DispatchOutcome}.
 *
 * This is where the gateway's `to_payload()` contract is interpreted. A `2xx`
 * body becomes `{ kind: "ok" }`; a non-OK body whose `action` names a known
 * handoff becomes `{ kind: "handoff" }` *and* is published on the event bus so a
 * decoupled wizard host can react; anything else becomes `{ kind: "error" }`.
 * Runs after the retry interceptor, so only *final* responses reach it.
 */

import type { GatewayEventBus } from "../events.js";
import type {
  DispatchOutcome,
  GatewayError,
  Handoff,
  HandoffAction,
} from "../types.js";

/** The actions this client knows how to surface. */
export const HANDOFF_ACTIONS: readonly HandoffAction[] = [
  "trigger_key_wizard",
  "upgrade_plan",
  "retry_later",
];

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

/** Type guard: does an arbitrary parsed body match the {@link Handoff} shape? */
export function isHandoffPayload(body: unknown): body is Handoff {
  if (!isRecord(body)) return false;
  return (
    typeof body["error"] === "string" &&
    typeof body["provider"] === "string" &&
    typeof body["action"] === "string" &&
    (HANDOFF_ACTIONS as readonly string[]).includes(body["action"])
  );
}

/** Parse a JSON body without throwing; returns `undefined` on empty/invalid. */
async function readJson(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return undefined;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return undefined;
  }
}

function toGatewayError(body: unknown, status: number): GatewayError {
  if (isRecord(body) && typeof body["error"] === "string") {
    const detail = body["detail"];
    return {
      error: body["error"],
      ...(typeof detail === "string" ? { detail } : {}),
    };
  }
  return { error: "unexpected_response", detail: `HTTP ${status}` };
}

/**
 * Decode a final response into a typed outcome.
 *
 * @param response - The response emerging from the interceptor chain.
 * @param bus - Event bus a handoff is published on before returning.
 */
export async function decodeOutcome<T>(
  response: Response,
  bus: GatewayEventBus,
): Promise<DispatchOutcome<T>> {
  const body = await readJson(response);

  if (response.ok) {
    return { kind: "ok", result: body as T };
  }

  if (isHandoffPayload(body)) {
    const handoff: Handoff = {
      error: body.error,
      provider: body.provider,
      action: body.action,
      ...(body.detail !== undefined ? { detail: body.detail } : {}),
    };
    bus.emit("handoff", { status: response.status, handoff });
    return { kind: "handoff", status: response.status, handoff };
  }

  return { kind: "error", status: response.status, error: toGatewayError(body, response.status) };
}
