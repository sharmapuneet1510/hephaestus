// Client for the Hephaestus backend API.

import type { ChatMessage } from "./types";

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  ai_configured: boolean;
  config: {
    server: { host: string; port: number };
    ai_configured: boolean;
    ai_endpoint_set: boolean;
    model_tiers: Record<string, string>;
    default_tier: string;
    ignore_paths: string[];
    context_max_tokens: number;
  };
}

/** Fetch backend health. Throws on network error or non-2xx response. */
export async function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const resp = await fetch("/api/health", { signal });
  if (!resp.ok) {
    throw new Error(`Backend returned ${resp.status}`);
  }
  return (await resp.json()) as HealthResponse;
}

/**
 * Stream a chat reply from the backend as an async generator of text deltas.
 * Parses the OpenAI-style SSE protocol (`data: {"delta": "..."}` … `[DONE]`).
 */
export async function* streamChat(
  messages: Pick<ChatMessage, "role" | "content">[],
  module: string | null,
  signal?: AbortSignal
): AsyncGenerator<string> {
  const resp = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages, module }),
    signal,
  });
  if (!resp.ok || !resp.body) {
    throw new Error(`Chat request failed (${resp.status})`);
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE events are separated by a blank line.
    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";

    for (const event of events) {
      const dataLine = event.split("\n").find((l) => l.startsWith("data: "));
      if (!dataLine) continue;
      const data = dataLine.slice("data: ".length);
      if (data === "[DONE]") return;
      try {
        const parsed = JSON.parse(data) as { delta?: string };
        if (parsed.delta) yield parsed.delta;
      } catch {
        // Ignore malformed keep-alive lines.
      }
    }
  }
}
