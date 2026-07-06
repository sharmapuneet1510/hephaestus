import { useCallback, useEffect, useState } from "react";
import { fetchHealth, streamChat } from "./api";
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

  // Action-bar handlers (SUBTASK 2.5). Placeholder behavior that produces
  // clearly visible state changes; real workflows arrive in later tasks.
  const handleAction = useCallback((action: ActionKind) => {
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
        case "save":
          return { ...s, lastAction: "Save Context", savedContexts: s.savedContexts + 1 };
        default:
          return s;
      }
    });
  }, []);

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
        <RepoTree />
        <ChatPanel messages={messages} streaming={streaming} onSend={sendMessage} />
        <StatusPanel status={status} busy={streaming} onAction={handleAction} />
      </div>
    </div>
  );
}
