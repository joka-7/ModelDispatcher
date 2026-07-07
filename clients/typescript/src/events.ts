/**
 * A tiny, strongly-typed event bus (Observer pattern).
 *
 * It exists to decouple *detecting* a Stage-2 handoff (deep inside the response
 * pipeline) from *reacting* to it (a wizard component that may live anywhere in
 * the tree). The interceptor publishes; {@link GatewayEventBus} fans the event
 * out to every subscriber without either side knowing about the other.
 */

import type { Handoff } from "./types.js";

/** Payload emitted whenever the gateway returns a structured handoff. */
export interface HandoffEvent {
  /** HTTP status the gateway chose: `402` (budget wall) or `429` (rate window). */
  readonly status: number;
  /** The decoded handoff instruction. */
  readonly handoff: Handoff;
}

/** The map of event names to their payload types. */
export interface GatewayEventMap {
  handoff: HandoffEvent;
}

/** Unsubscribe handle returned by {@link GatewayEventBus.on}. */
export type Unsubscribe = () => void;

/** Listener signature for a given event. */
export type Listener<E extends keyof GatewayEventMap> = (
  event: GatewayEventMap[E],
) => void;

/**
 * Synchronous, in-memory pub/sub for gateway events.
 *
 * Listener exceptions are swallowed (and forwarded to `onListenerError` when
 * provided) so one bad subscriber can never break delivery to the others.
 */
export class GatewayEventBus {
  readonly #listeners: {
    [E in keyof GatewayEventMap]: Set<Listener<E>>;
  } = { handoff: new Set() };

  readonly #onListenerError: (error: unknown) => void;

  constructor(onListenerError: (error: unknown) => void = () => {}) {
    this.#onListenerError = onListenerError;
  }

  /**
   * Subscribe to an event.
   *
   * @returns A function that removes this exact listener when called.
   */
  on<E extends keyof GatewayEventMap>(event: E, listener: Listener<E>): Unsubscribe {
    this.#listeners[event].add(listener);
    return () => {
      this.#listeners[event].delete(listener);
    };
  }

  /** Publish an event to every current subscriber. */
  emit<E extends keyof GatewayEventMap>(event: E, payload: GatewayEventMap[E]): void {
    for (const listener of this.#listeners[event]) {
      try {
        listener(payload);
      } catch (error) {
        this.#onListenerError(error);
      }
    }
  }

  /** Remove all listeners (useful in test teardown). */
  clear(): void {
    this.#listeners.handoff.clear();
  }
}
