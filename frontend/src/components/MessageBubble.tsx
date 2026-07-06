import { motion } from "framer-motion";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import type { Components } from "react-markdown";
import type { ChatMessage } from "../types";
import { CodeBlock } from "./CodeBlock";
import { DiffView } from "./DiffView";

/** Heuristic: does this assistant content look like a unified diff? */
function isUnifiedDiff(content: string): boolean {
  const t = content.trimStart();
  return t.startsWith("--- ") || t.startsWith("diff --git") || /\n@@ .* @@/.test(content);
}

// Route fenced code blocks (rendered by react-markdown as <pre><code>) through
// our CodeBlock. Inline code falls through to default rendering.
const markdownComponents: Components = {
  pre: ({ children }) => <>{children}</>,
  code({ className, children, ...props }) {
    const isBlock = /language-/.test(className ?? "");
    if (isBlock) {
      return <CodeBlock className={className}>{children}</CodeBlock>;
    }
    return (
      <code className={className} {...props}>
        {children}
      </code>
    );
  },
};

export function MessageBubble({ message }: { message: ChatMessage }) {
  const isAssistant = message.role === "assistant";
  return (
    <motion.div
      className={`msg ${isAssistant ? "msg--assistant" : "msg--user"}`}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
    >
      <div className="msg__avatar">{isAssistant ? "H" : "you"}</div>
      <div className="msg__body">
        <div className="msg__role">{isAssistant ? "Hephaestus" : "You"}</div>
        {isAssistant && !message.streaming && isUnifiedDiff(message.content) ? (
          <DiffView diff={message.content} />
        ) : isAssistant ? (
          <div className="md">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeHighlight]}
              components={markdownComponents}
            >
              {message.content}
            </ReactMarkdown>
            {message.streaming && <span className="caret" aria-hidden="true" />}
          </div>
        ) : (
          <div className="md">
            <p style={{ whiteSpace: "pre-wrap" }}>{message.content}</p>
          </div>
        )}
      </div>
    </motion.div>
  );
}
