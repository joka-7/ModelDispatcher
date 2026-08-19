/**
 * Shared HTTP plumbing every provider call needs: a request timeout merged
 * with the caller's own AbortSignal, one retry on a transient (429/5xx)
 * failure, Ollama URL validation, and a line-buffered stream reader so each
 * provider's stream parser only has to know its own line format.
 */

export const DEFAULT_TIMEOUT_MS = 60_000;
const RETRY_DELAY_MS = 600;

/** A hung provider (dropped connection, stalled proxy) would otherwise hang
 * forever — fetch() has no default timeout. Merges an optional caller signal
 * (e.g. "abort because the component unmounted") with a hard ceiling. */
export function requestSignal(
  signal?: AbortSignal,
  timeoutMs: number = DEFAULT_TIMEOUT_MS,
): AbortSignal {
  const timeoutSignal = AbortSignal.timeout(timeoutMs);
  return signal ? AbortSignal.any([signal, timeoutSignal]) : timeoutSignal;
}

function isRetryableStatus(status: number): boolean {
  return status === 429 || (status >= 500 && status < 600);
}

/**
 * fetch() with one retry on a 429/5xx or a network failure. An
 * externally-aborted request (unmount, a newer request superseding this
 * one) is never retried — that's a deliberate cancellation, not a
 * transient failure, and retrying it would just start a request nobody
 * wants the result of anymore.
 */
export async function fetchWithRetry(
  url: string,
  init: RequestInit,
  externalSignal?: AbortSignal,
  timeoutMs: number = DEFAULT_TIMEOUT_MS,
): Promise<Response> {
  for (let attempt = 0; ; attempt++) {
    try {
      const res = await fetch(url, { ...init, signal: requestSignal(externalSignal, timeoutMs) });
      if (attempt === 0 && isRetryableStatus(res.status)) {
        await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY_MS));
        continue;
      }
      return res;
    } catch (err) {
      if (externalSignal?.aborted || attempt > 0) throw err;
      await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY_MS));
    }
  }
}

/** Reject a remote Ollama URL that isn't HTTPS (localhost is exempt — that's
 * the whole point of running it locally). Returns the normalised origin. */
export function validateOllamaUrl(url: string): string {
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch (err) {
    throw new Error(`Invalid Ollama URL: ${(err as Error).message}`, { cause: err });
  }
  const isLocalhost = ["localhost", "127.0.0.1", "::1"].includes(parsed.hostname);
  if (!isLocalhost && parsed.protocol !== "https:") {
    throw new Error("Remote Ollama must use HTTPS. For local testing, use http://localhost:11434");
  }
  return parsed.origin;
}

/** A 200 with no body (adblocker, misbehaving proxy) would otherwise throw a
 * raw TypeError on getReader() deep inside the parser. */
function getBodyReader(res: Response): ReadableStreamDefaultReader<Uint8Array> {
  if (!res.body) throw new Error("Empty response body from AI provider.");
  return res.body.getReader();
}

/** Feeds each complete line of a streamed response body to `onLine`, so
 * every provider's stream parser only needs to know its own line format
 * (SSE "data: " frames vs. bare NDJSON). */
export async function consumeLines(res: Response, onLine: (line: string) => void): Promise<void> {
  const reader = getBodyReader(res);
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) onLine(line);
  }
}

/** Extract a provider's error message from a JSON error body, falling back
 * to the raw HTTP status when the body isn't shaped as expected. */
export async function describeHttpError(res: Response): Promise<string> {
  const body: unknown = await res.json().catch(() => ({}));
  const message = (body as { error?: { message?: string } })?.error?.message;
  return message ?? `HTTP ${res.status}`;
}
