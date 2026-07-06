import { useState, type ReactNode } from "react";

/**
 * Custom renderer for fenced code blocks (SUBTASK 2.4). rehype-highlight has
 * already added `.hljs` token spans to the children; we add a language label
 * and a copy button around them.
 */
export function CodeBlock({
  className,
  children,
}: {
  className?: string;
  children?: ReactNode;
}) {
  const [copied, setCopied] = useState(false);
  const lang = /language-(\w+)/.exec(className ?? "")?.[1] ?? "text";

  const copy = () => {
    const text = extractText(children);
    void navigator.clipboard?.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1400);
    });
  };

  return (
    <div className="code">
      <div className="code__bar">
        <span className="code__lang">{lang}</span>
        <button className="code__copy" onClick={copy} type="button">
          {copied ? "copied ✓" : "copy"}
        </button>
      </div>
      <pre>
        <code className={className}>{children}</code>
      </pre>
    </div>
  );
}

function extractText(node: ReactNode): string {
  if (node == null || typeof node === "boolean") return "";
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(extractText).join("");
  if (typeof node === "object" && "props" in node) {
    return extractText((node as { props: { children?: ReactNode } }).props.children);
  }
  return "";
}
