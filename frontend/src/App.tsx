import { useCallback, useEffect, useMemo, useState } from "react";
import {
  approvePlan,
  buildContext,
  editStatus,
  fetchHealth,
  generatePlan,
  revertEdits,
  streamChat,
  tryEdit,
  type Plan,
  type RepoMetadata,
  type TreeNode,
} from "./api";
import type { ChatMessage, WorkspaceStatus } from "./types";
import { Header, type ConnState } from "./components/Header";
import { RepoTree } from "./components/RepoTree";
import { ChatPanel } from "./components/ChatPanel";
import { StatusPanel, type ActionKind } from "./components/StatusPanel";

const INITIAL_STATUS: WorkspaceStatus = {
  currentTask: "Idle",
  moduleFocus: null,
  filesTouched: [],
  testStatus: "idle",
  lastAction: null,
  savedContexts: 0,
};

let idCounter = 0;
const nextId = () => `m${++idCounter}`;

/** Render a structured plan as markdown for the chat (TASK 7.1). */
function planToMarkdown(plan: Plan): string {
  const list = (items: string[]) => items.map((i) => `- ${i}`).join("\n");
  const files = plan.files_to_change.length
    ? list(plan.files_to_change)
    : "- _(determined after inspection)_";
  return [
    `**Plan**`,
    ``,
    `**Goal:** ${plan.goal}`,
    ``,
    `**Files likely to change**\n${files}`,
    ``,
    `**Steps**\n${plan.steps.map((s, i) => `${i + 1}. ${s}`).join("\n")}`,
    ``,
    `**Risks**\n${list(plan.risks)}`,
    ``,
    `**Tests**\n${list(plan.tests)}`,
    ``,
    `**Expected output:** ${plan.expected_output}`,
    ``,
    `_Review, then click **Apply** to proceed._`,
  ].join("\n");
}

export function App() {
  const [conn, setConn] = useState<ConnState>({ kind: "connecting" });
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [status, setStatus] = useState<WorkspaceStatus>(INITIAL_STATUS);
  const [repo, setRepo] = useState<RepoMetadata | null>(null);
  const [repoTree, setRepoTree] = useState<TreeNode | null>(null);
  const [pendingPlan, setPendingPlan] = useState<Plan | null>(null);

  // Directory paths available for module focus (TASK 6).
  const moduleDirs = useMemo(() => {
    const dirs: string[] = [];
    const walk = (node: TreeNode) => {
      for (const child of node.children ?? []) {
        if (child.type === "dir") {
          dirs.push(child.path);
          walk(child);
        }
      }
    };
    if (repoTree) walk(repoTree);
    return dirs;
  }, [repoTree]);

  // Sync the touched-files list from the backend edit session (SUBTASK 8.5).
  const syncEdits = useCallback(() => {
    editStatus()
      .then((files) => setStatus((s) => ({ ...s, filesTouched: files })))
      .catch(() => {});
  }, []);

  const handleRepoLoaded = useCallback(
    (meta: RepoMetadata | null, tree: TreeNode | null) => {
      setRepo(meta);
      setRepoTree(tree);
      setStatus((s) => ({ ...s, moduleFocus: null })); // reset focus for the new repo
      syncEdits();
    },
    [syncEdits]
  );

  // Startup: confirm backend connection (carried over from TASK 1).
  useEffect(() => {
    const controller = new AbortController();
    fetchHealth(controller.signal)
      .then((health) => setConn({ kind: "connected", health }))
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setConn({ kind: "error", message: err instanceof Error ? err.message : "Unknown error" });
      });
    return () => controller.abort();
  }, []);

  const sendMessage = useCallback(
    async (text: string) => {
      if (streaming) return;
      const trimmed = text.trim();

      // Module focus commands (SUBTASK 6.2 / 6.4) — handled locally, no AI call.
      if (/^(?:clear focus|unfocus|remove focus)$/i.test(trimmed)) {
        setStatus((s) => ({ ...s, moduleFocus: null }));
        setMessages((prev) => [
          ...prev,
          { id: nextId(), role: "user", content: text },
          { id: nextId(), role: "assistant", content: "Cleared module focus." },
        ]);
        return;
      }
      const focusMatch = trimmed.match(/^focus on (?:the )?(.+?)(?: module)?$/i);
      if (focusMatch) {
        const target = focusMatch[1].trim().toLowerCase();
        let note: string;
        if (!repo) {
          note = "Load a repository first, then set a module focus.";
        } else {
          const resolved =
            moduleDirs.find((d) => d.toLowerCase() === target) ??
            moduleDirs.find((d) => d.split("/").pop()?.toLowerCase() === target) ??
            moduleDirs.find((d) => d.toLowerCase().endsWith(`/${target}`)) ??
            null;
          if (resolved) {
            setStatus((s) => ({ ...s, moduleFocus: resolved }));
            note = `Focused on module \`${resolved}\`.`;
          } else {
            note = `No module matching "${focusMatch[1].trim()}". Try a folder name from the tree.`;
          }
        }
        setMessages((prev) => [
          ...prev,
          { id: nextId(), role: "user", content: text },
          { id: nextId(), role: "assistant", content: note },
        ]);
        return;
      }

      const userMsg: ChatMessage = { id: nextId(), role: "user", content: text };
      const assistantId = nextId();

      // Build the outbound history from the messages known at send time.
      const history = [...messages, userMsg].map((m) => ({ role: m.role, content: m.content }));

      setMessages((prev) => [
        ...prev,
        userMsg,
        { id: assistantId, role: "assistant", content: "", streaming: true },
      ]);
      setStreaming(true);
      setStatus((s) => ({ ...s, currentTask: "Thinking…" }));

      try {
        for await (const delta of streamChat(history, status.moduleFocus)) {
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantId ? { ...m, content: m.content + delta } : m))
          );
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : "stream failed";
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? { ...m, content: `⚠️ Could not reach the assistant: ${message}` }
              : m
          )
        );
      } finally {
        setMessages((prev) =>
          prev.map((m) => (m.id === assistantId ? { ...m, streaming: false } : m))
        );
        setStreaming(false);
        setStatus((s) => ({ ...s, currentTask: "Idle" }));
      }
    },
    [messages, streaming, status.moduleFocus, repo, moduleDirs]
  );

  // Save Context builds real context for the loaded repo (TASK 5); when no repo
  // is loaded it just records the action.
  const saveContext = useCallback(async () => {
    setStatus((s) => ({ ...s, lastAction: "Save Context" }));
    if (!repo) {
      setStatus((s) => ({ ...s, savedContexts: s.savedContexts + 1 }));
      return;
    }
    setStatus((s) => ({ ...s, currentTask: "Building context…" }));
    try {
      const res = await buildContext(status.moduleFocus);
      setStatus((s) => ({
        ...s,
        savedContexts: s.savedContexts + 1,
        currentTask: `Context: ${res.file_count} files, ${res.chunk_count} chunks`,
      }));
    } catch {
      setStatus((s) => ({ ...s, currentTask: "Context build failed" }));
    }
  }, [repo, status.moduleFocus]);

  const addNote = useCallback((content: string) => {
    setMessages((prev) => [...prev, { id: nextId(), role: "assistant", content }]);
  }, []);

  // Plan-first (TASK 7): generate a structured plan for the latest request.
  const runPlan = useCallback(async () => {
    setStatus((s) => ({ ...s, lastAction: "Plan" }));
    const lastUser = [...messages].reverse().find((m) => m.role === "user");
    if (!lastUser) {
      addNote("Describe the change you want (send a message), then click Plan.");
      return;
    }
    setStatus((s) => ({ ...s, currentTask: "Planning…" }));
    try {
      const plan = await generatePlan(lastUser.content, status.moduleFocus);
      setPendingPlan(plan);
      addNote(planToMarkdown(plan));
      setStatus((s) => ({ ...s, currentTask: "Plan ready — review, then Apply" }));
    } catch {
      setStatus((s) => ({ ...s, currentTask: "Plan failed" }));
    }
  }, [messages, status.moduleFocus, addNote]);

  // Apply approves the pending plan and passes the edit guard (TASK 7.4). Actual
  // per-file patches are applied via applyEdit once the assistant proposes them
  // (TASK 8 backend); here we open the gate and sync touched files.
  const runApply = useCallback(async () => {
    if (!pendingPlan) return;
    setStatus((s) => ({ ...s, lastAction: "Apply", currentTask: "Applying…" }));
    try {
      await approvePlan();
      const res = await tryEdit();
      addNote(res.message);
      syncEdits();
      setStatus((s) => ({ ...s, currentTask: "Plan applied" }));
    } catch (err) {
      addNote(`⚠️ ${err instanceof Error ? err.message : "Apply blocked"}`);
      setStatus((s) => ({ ...s, currentTask: "Apply blocked" }));
    }
  }, [pendingPlan, addNote, syncEdits]);

  // Revert restores any edited files via the backend (SUBTASK 8.4).
  const runRevert = useCallback(async () => {
    setPendingPlan(null);
    setStatus((s) => ({ ...s, lastAction: "Revert", testStatus: "idle" }));
    try {
      const reverted = await revertEdits();
      addNote(
        reverted.length
          ? `Reverted ${reverted.length} file(s): ${reverted.join(", ")}.`
          : "Nothing to revert."
      );
    } catch {
      /* ignore */
    }
    syncEdits();
  }, [addNote, syncEdits]);

  // Action-bar handlers. Plan/Apply are wired to TASK 7; Save Context to TASK 5;
  // Test/Revert remain placeholders (real workflows land in TASK 8/9).
  const handleAction = useCallback(
    (action: ActionKind) => {
      if (action === "save") return void saveContext();
      if (action === "plan") return void runPlan();
      if (action === "apply") return void runApply();
      if (action === "revert") return void runRevert();
      if (action === "test") setStatus((s) => ({ ...s, lastAction: "Test", testStatus: "running" }));
    },
    [saveContext, runPlan, runApply, runRevert]
  );

  // Resolve the mock "Test" run shortly after it starts.
  useEffect(() => {
    if (status.testStatus !== "running") return;
    const t = setTimeout(() => setStatus((s) => ({ ...s, testStatus: "passed" })), 900);
    return () => clearTimeout(t);
  }, [status.testStatus]);

  return (
    <div className="app">
      <Header conn={conn} streaming={streaming} />
      <div className="workspace">
        <RepoTree
          focus={status.moduleFocus}
          onRepoLoaded={handleRepoLoaded}
          onSetFocus={(path) => setStatus((s) => ({ ...s, moduleFocus: path }))}
        />
        <ChatPanel messages={messages} streaming={streaming} onSend={sendMessage} />
        <StatusPanel
          status={status}
          busy={streaming}
          applyDisabled={!pendingPlan}
          onAction={handleAction}
          onClearFocus={() => setStatus((s) => ({ ...s, moduleFocus: null }))}
        />
      </div>
    </div>
  );
}
