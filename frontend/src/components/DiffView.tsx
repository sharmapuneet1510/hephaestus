// Renders a unified diff with per-line add/remove/hunk styling (SUBTASK 8.3).

export function DiffView({ diff }: { diff: string }) {
  const lines = diff.replace(/\n$/, "").split("\n");
  return (
    <pre className="diff" data-testid="diff-view">
      <code>
        {lines.map((line, i) => {
          let cls = "";
          if (line.startsWith("+") && !line.startsWith("+++")) cls = "diff-add";
          else if (line.startsWith("-") && !line.startsWith("---")) cls = "diff-del";
          else if (line.startsWith("@@")) cls = "diff-hunk";
          return (
            <div key={i} className={`diff-line${cls ? ` ${cls}` : ""}`}>
              {line || " "}
            </div>
          );
        })}
      </code>
    </pre>
  );
}
