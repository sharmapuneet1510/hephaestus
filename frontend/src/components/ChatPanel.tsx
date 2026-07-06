import { useEffect, useRef } from "react";
import type { ChatMessage } from "../types";
import { MessageBubble } from "./MessageBubble";
import { Composer } from "./Composer";

const SUGGESTIONS = [
  "Explain this repository's structure",
  "Plan a fix for the failing test",
  "Add input validation to the login form",
];

export function ChatPanel({
  messages,
  streaming,
  onSend,
}: {
  messages: ChatMessage[];
  streaming: boolean;
  onSend: (text: string) => void;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  return (
    <main className="panel panel--chat" aria-label="Chat">
      <div className="chat__scroll" ref={scrollRef}>
        {messages.length === 0 ? (
          <div className="chat__welcome">
            <h1>What shall we forge?</h1>
            <p>
              Hephaestus plans before it changes code, shows diffs, and runs tests. Ask a question or
              request a change to begin.
            </p>
            <div className="chat__suggestions">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  className="suggestion"
                  type="button"
                  onClick={() => onSend(s)}
                  disabled={streaming}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((m) => <MessageBubble key={m.id} message={m} />)
        )}
      </div>
      <Composer disabled={streaming} onSend={onSend} />
    </main>
  );
}
