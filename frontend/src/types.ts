// Shared frontend types.

export type Role = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: Role;
  content: string;
  /** True while the assistant message is still streaming in. */
  streaming?: boolean;
}

export type TestStatus = "idle" | "running" | "passed" | "failed";

/** Right-panel workspace state. */
export interface WorkspaceStatus {
  currentTask: string;
  moduleFocus: string | null;
  filesTouched: string[];
  testStatus: TestStatus;
  lastAction: string | null;
  savedContexts: number;
  /** Routed model tier for the last assistant turn (TASK 13.3). */
  modelTier: string | null;
}
