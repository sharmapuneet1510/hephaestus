import { useCallback, useEffect, useState } from "react";
import { buildContext, fetchHealth, streamChat, type RepoMetadata } from "./api";
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
    [messages, streaming, status.moduleFocus]
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
        <RepoTree onRepoLoaded={setRepo} />
        <ChatPanel messages={messages} streaming={streaming} onSend={sendMessage} />
        <StatusPanel status={status} busy={streaming} onAction={handleAction} />
      </div>
    </div>
  );
}
