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

// ---- Repository (TASK 4) ----
export interface TreeNode {
  name: string;
  path: string;
  type: "dir" | "file";
  size?: number;
  children?: TreeNode[];
}

export interface RepoMetadata {
  path: string;
  name: string;
  project_type: string;
  file_count: number;
  truncated: boolean;
  loaded_at: string;
}

/** Load a local repository by path. Throws with the backend's message on failure. */
export async function loadRepository(
  path: string
): Promise<{ metadata: RepoMetadata; tree: TreeNode }> {
  const resp = await fetch("/api/repo/load", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path }),
  });
  if (!resp.ok) {
    let detail = `Failed to load repository (${resp.status})`;
    try {
      detail = ((await resp.json()) as { detail?: string }).detail ?? detail;
    } catch {
      /* keep default */
    }
    throw new Error(detail);
  }
  return (await resp.json()) as { metadata: RepoMetadata; tree: TreeNode };
}

/** Fetch the last-loaded repo metadata (null if none). */
export async function fetchRepository(signal?: AbortSignal): Promise<RepoMetadata | null> {
  const resp = await fetch("/api/repo", { signal });
  if (!resp.ok) return null;
  return ((await resp.json()) as { metadata: RepoMetadata | null }).metadata;
}

// ---- Test runner (TASK 9) ----
export interface TestResult {
  command: string;
  exit_code: number;
  passed: boolean;
  duration_ms: number;
  summary: string;
  output: string;
  failed_files: string[];
}

/** Run the detected (or given) test command for the loaded repo. */
export async function runTests(command: string | null = null): Promise<TestResult> {
  const resp = await fetch("/api/test", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command }),
  });
  if (!resp.ok) {
    let detail = `Test run failed (${resp.status})`;
    try {
      detail = ((await resp.json()) as { detail?: string }).detail ?? detail;
    } catch {
      /* keep default */
    }
    throw new Error(detail);
  }
  return (await resp.json()) as TestResult;
}

// ---- File editing (TASK 8) ----
export interface ApplyResult {
  path: string;
  created: boolean;
  diff: string;
  touched: string[];
}

/** Apply an edit to a file (blocked by the backend unless a plan is approved). */
export async function applyEdit(path: string, newContent: string): Promise<ApplyResult> {
  const resp = await fetch("/api/edit/apply", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path, new_content: newContent }),
  });
  if (!resp.ok) {
    let detail = `Edit blocked (${resp.status})`;
    try {
      detail = ((await resp.json()) as { detail?: string }).detail ?? detail;
    } catch {
      /* keep default */
    }
    throw new Error(detail);
  }
  return (await resp.json()) as ApplyResult;
}

/** Revert all edits applied this session. Returns the reverted paths. */
export async function revertEdits(): Promise<string[]> {
  const resp = await fetch("/api/edit/revert", { method: "POST" });
  if (!resp.ok) throw new Error(`Revert failed (${resp.status})`);
  return ((await resp.json()) as { reverted: string[] }).reverted;
}

/** List files touched in this edit session (SUBTASK 8.5). */
export async function editStatus(): Promise<string[]> {
  const resp = await fetch("/api/edit/status");
  if (!resp.ok) return [];
  return ((await resp.json()) as { files: string[] }).files;
}

// ---- Context engine (TASK 5) ----
export interface ContextResult {
  module: string | null;
  format: string;
  file_count: number;
  chunk_count: number;
  content?: string;
  data?: unknown;
}

// ---- Plan-first workflow (TASK 7) ----
export interface Plan {
  goal: string;
  files_to_change: string[];
  steps: string[];
  risks: string[];
  tests: string[];
  expected_output: string;
}

/** Generate a structured plan for a change request. */
export async function generatePlan(message: string, module: string | null = null): Promise<Plan> {
  const resp = await fetch("/api/plan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, module }),
  });
  if (!resp.ok) throw new Error(`Plan failed (${resp.status})`);
  return ((await resp.json()) as { plan: Plan }).plan;
}

/** Approve the current pending plan (required before editing). */
export async function approvePlan(): Promise<void> {
  const resp = await fetch("/api/plan/approve", { method: "POST" });
  if (!resp.ok) throw new Error(`Approve failed (${resp.status})`);
}

/** Attempt an edit — blocked by the backend unless an approved plan exists. */
export async function tryEdit(): Promise<{ ok: boolean; message: string }> {
  const resp = await fetch("/api/edit", { method: "POST" });
  if (!resp.ok) {
    let detail = `Edit blocked (${resp.status})`;
    try {
      detail = ((await resp.json()) as { detail?: string }).detail ?? detail;
    } catch {
      /* keep default */
    }
    throw new Error(detail);
  }
  return (await resp.json()) as { ok: boolean; message: string };
}

/** Build context for the loaded repo (throws if none is loaded / on failure). */
export async function buildContext(
  module: string | null = null,
  format: "markdown" | "json" | "toon" | "graph" = "markdown"
): Promise<ContextResult> {
  const resp = await fetch("/api/context/build", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ module, format }),
  });
  if (!resp.ok) {
    throw new Error(`Context build failed (${resp.status})`);
  }
  return (await resp.json()) as ContextResult;
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
