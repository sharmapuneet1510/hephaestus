import { useCallback, useEffect, useMemo, useState } from "react";
import {
  buildContext,
  fetchHealth,
  streamChat,
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

export function App() {
  const [conn, setConn] = useState<ConnState>({ kind: "connecting" });
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [status, setStatus] = useState<WorkspaceStatus>(INITIAL_STATUS);
  const [repo, setRepo] = useState<RepoMetadata | null>(null);
  const [repoTree, setRepoTree] = useState<TreeNode | null>(null);

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

  const handleRepoLoaded = useCallback((meta: RepoMetadata | null, tree: TreeNode | null) => {
    setRepo(meta);
    setRepoTree(tree);
    setStatus((s) => ({ ...s, moduleFocus: null })); // reset focus for the new repo
  }, []);

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

  // Action-bar handlers (SUBTASK 2.5). Plan/Apply/Test/Revert are placeholders
  // (real workflows arrive in later tasks); Save Context is wired to TASK 5.
  const handleAction = useCallback(
    (action: ActionKind) => {
      if (action === "save") {
        void saveContext();
        return;
      }
      setStatus((s) => {
        switch (action) {
          case "plan":
            return { ...s, lastAction: "Plan", currentTask: "Planning change" };
          case "apply":
            return {
              ...s,
              lastAction: "Apply",
              currentTask: "Applied edit",
              filesTouched: Array.from(new Set([...s.filesTouched, "src/example.ts"])),
            };
          case "test":
            return { ...s, lastAction: "Test", testStatus: "running" };
          case "revert":
            return { ...s, lastAction: "Revert", filesTouched: [], testStatus: "idle" };
          default:
            return s;
        }
      });
    },
    [saveContext]
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
          onAction={handleAction}
          onClearFocus={() => setStatus((s) => ({ ...s, moduleFocus: null }))}
        />
      </div>
    </div>
  );
}
