/**
 * Tool calling in the browser: the model asks for tools, the app runs them
 * on the device, and the results go back until the model answers. The same
 * bounded loop as the Python core's `AgentLoop`, client-side.
 *
 *   - runWithTools() — a chat history and a set of tools in, the final answer
 *     and the tools used out
 *
 * Each turn is dispatched through the same fallback list as `complete()`, so
 * a failing provider hands the run to the next one mid-conversation: the
 * history is kept in a neutral form ({@link ToolChatMessage}) and translated
 * per provider on every turn. Non-streaming: a turn may end in tool calls,
 * so there is no single text stream to show.
 */

import {
  AllProvidersExhaustedError,
  candidatesOf,
  NoProviderConfiguredError,
  type FailedAttempt,
} from "./agent.js";
import { completeWithToolsAnthropic } from "./providers/anthropic.js";
import { completeWithToolsGemini } from "./providers/gemini.js";
import { completeWithToolsOllama } from "./providers/ollama.js";
import { completeWithToolsOpenAICompatible } from "./providers/openaiCompatible.js";
import type {
  AgentConfig,
  ProviderCallConfig,
  ProviderId,
  RequestOptions,
  ToolCall,
  ToolChatMessage,
  ToolResult,
  ToolSpec,
  ToolTurn,
} from "./types.js";

/** A tool the app runs itself: its declaration and its implementation. */
export interface Tool {
  readonly spec: ToolSpec;
  /** Runs on the device with the model's decoded arguments; its return value
   * (or the message of what it throws) is what the model reads. */
  readonly run: (args: Readonly<Record<string, unknown>>) => string | Promise<string>;
}

export interface RunWithToolsOptions extends Omit<RequestOptions, "jsonMode"> {
  readonly tools: readonly Tool[];
  /** Model turns allowed before giving up (each may request several tools).
   * Defaults to {@link DEFAULT_MAX_STEPS}. */
  readonly maxSteps?: number;
  /** Called after each tool runs, e.g. to show "looked up AAPL" while waiting. */
  readonly onToolResult?: (call: ToolCall, result: ToolResult) => void;
}

export type ToolRunStopReason = "completed" | "max_steps";

export interface ToolRunResult {
  /** The model's final answer; may be empty when `stopReason` is "max_steps". */
  readonly text: string;
  readonly stopReason: ToolRunStopReason;
  /** Names of the tools run, in order, repeats included. */
  readonly toolsUsed: readonly string[];
  /** The provider and model that produced the final turn. */
  readonly provider: ProviderId;
  readonly model: string;
  /** The whole conversation including tool turns, to continue it later. */
  readonly messages: readonly ToolChatMessage[];
}

export const DEFAULT_MAX_STEPS = 6;

function completeTurn(
  candidate: ProviderCallConfig,
  messages: readonly ToolChatMessage[],
  tools: readonly ToolSpec[],
  options: RequestOptions,
): Promise<ToolTurn> {
  switch (candidate.provider) {
    case "gemini":
      return completeWithToolsGemini(candidate, messages, tools, options);
    case "anthropic":
      return completeWithToolsAnthropic(candidate, messages, tools, options);
    case "ollama":
      return completeWithToolsOllama(candidate, messages, tools, options);
    case "openai":
    case "groq":
      return completeWithToolsOpenAICompatible(candidate.provider, candidate, messages, tools, options);
  }
}

interface DispatchedTurn {
  readonly turn: ToolTurn;
  readonly candidate: ProviderCallConfig;
}

async function dispatchTurn(
  candidates: readonly ProviderCallConfig[],
  messages: readonly ToolChatMessage[],
  tools: readonly ToolSpec[],
  options: RequestOptions,
): Promise<DispatchedTurn> {
  const attempts: FailedAttempt[] = [];
  for (const candidate of candidates) {
    try {
      return { turn: await completeTurn(candidate, messages, tools, options), candidate };
    } catch (err) {
      if (options.signal?.aborted) throw err;
      attempts.push({ provider: candidate.provider, error: messageOf(err) });
    }
  }
  throw new AllProvidersExhaustedError(attempts);
}

/**
 * Give calls without a provider id (Gemini, Ollama) one unique in the whole
 * conversation, counting the calls already in it: a continued conversation
 * must not repeat an id (Anthropic rejects duplicates).
 */
function numberCalls(calls: readonly ToolCall[], history: readonly ToolChatMessage[]): ToolCall[] {
  let next = history.reduce((n, m) => n + ("toolCalls" in m ? m.toolCalls.length : 0), 0);
  return calls.map((call) => (call.id ? call : { ...call, id: `call_${next++}` }));
}

function messageOf(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

/**
 * The system prompt for every turn, decided once so a fallback doesn't change
 * it: the explicit option, else every system turn in the history, joined.
 */
function systemOf(messages: readonly ToolChatMessage[], explicit: string | undefined): string | undefined {
  if (explicit !== undefined) return explicit;
  const turns = messages.flatMap((m) => (m.role === "system" ? [m.content] : []));
  return turns.length ? turns.join("\n\n") : undefined;
}

/** What goes to the provider: no system turns (sent as the instruction) and no
 * empty plain turns, which Anthropic and Gemini reject. */
function sendable(history: readonly ToolChatMessage[]): ToolChatMessage[] {
  return history.filter((m) => m.role !== "system" && (m.role === "tool" || "toolCalls" in m || m.content !== ""));
}

async function runTool(tools: ReadonlyMap<string, Tool>, call: ToolCall): Promise<ToolResult> {
  const tool = tools.get(call.name);
  if (!tool) return { callId: call.id, name: call.name, content: `unknown tool: ${call.name}`, isError: true };
  try {
    return { callId: call.id, name: call.name, content: await tool.run(call.arguments), isError: false };
  } catch (err) {
    // Handed back to the model, which can retry or explain, as the Python core does.
    return { callId: call.id, name: call.name, content: `tool error: ${messageOf(err)}`, isError: true };
  }
}

/**
 * Run a conversation in which the model may call `options.tools`, until it
 * answers without asking for one or `maxSteps` turns pass. Tools run one at
 * a time, in the order asked, so a write lands before a later read.
 *
 * Raises:
 *   NoProviderConfiguredError: `cfg.providers` has no usable credential.
 *   AllProvidersExhaustedError: every candidate failed on some turn.
 */
export async function runWithTools(
  cfg: AgentConfig,
  messages: readonly ToolChatMessage[],
  options: RunWithToolsOptions,
): Promise<ToolRunResult> {
  const candidates = candidatesOf(cfg);
  if (candidates.length === 0) throw new NoProviderConfiguredError();
  const { tools, maxSteps = DEFAULT_MAX_STEPS, onToolResult, systemInstruction, ...rest } = options;
  const system = systemOf(messages, systemInstruction);
  const requestOptions: RequestOptions = system === undefined ? rest : { ...rest, systemInstruction: system };
  const specs = tools.map((t) => t.spec);
  const byName = new Map(tools.map((t) => [t.spec.name, t]));

  const history: ToolChatMessage[] = [...messages];
  const toolsUsed: string[] = [];
  let last: DispatchedTurn | undefined;
  for (let step = 0; step < maxSteps; step++) {
    last = await dispatchTurn(candidates, sendable(history), specs, requestOptions);
    const calls = numberCalls(last.turn.toolCalls, history);
    if (calls.length === 0) {
      if (last.turn.text) history.push({ role: "assistant", content: last.turn.text });
      return result(last, "completed", toolsUsed, history);
    }
    history.push({ role: "assistant", content: last.turn.text, toolCalls: calls });
    const results: ToolResult[] = [];
    for (const call of calls) {
      const outcome = await runTool(byName, call);
      toolsUsed.push(call.name);
      results.push(outcome);
      onToolResult?.(call, outcome);
    }
    history.push({ role: "tool", results });
  }
  if (!last) throw new RangeError(`maxSteps must be at least 1, got ${maxSteps}`);
  return result(last, "max_steps", toolsUsed, history);
}

function result(
  last: DispatchedTurn,
  stopReason: ToolRunStopReason,
  toolsUsed: readonly string[],
  history: readonly ToolChatMessage[],
): ToolRunResult {
  return {
    text: last.turn.text,
    stopReason,
    toolsUsed,
    provider: last.candidate.provider,
    model: last.candidate.model,
    messages: history,
  };
}
