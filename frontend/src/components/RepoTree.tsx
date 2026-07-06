import { useEffect, useState } from "react";
import { fetchRepository, loadRepository, type RepoMetadata, type TreeNode } from "../api";

// Left panel — repository loader + file tree (TASK 4). The user pastes a local
// path; the backend scans it (honoring ignore rules) and returns the tree.

type LoadState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "loaded"; repo: RepoMetadata; tree: TreeNode }
  | { kind: "error"; message: string };

export function RepoTree({ onRepoLoaded }: { onRepoLoaded?: (repo: RepoMetadata | null) => void }) {
  const [path, setPath] = useState("");
  const [state, setState] = useState<LoadState>({ kind: "idle" });

  const load = async (target: string) => {
    const trimmed = target.trim();
    if (!trimmed) return;
    setState({ kind: "loading" });
    try {
      const { metadata, tree } = await loadRepository(trimmed);
      setState({ kind: "loaded", repo: metadata, tree });
      onRepoLoaded?.(metadata);
    } catch (err) {
      setState({ kind: "error", message: err instanceof Error ? err.message : "Load failed" });
      onRepoLoaded?.(null);
    }
  };

  // Restore the last-loaded repo on mount (SUBTASK 4.5).
  useEffect(() => {
    const controller = new AbortController();
    fetchRepository(controller.signal)
      .then((meta) => {
        if (meta) {
          setPath(meta.path);
          void load(meta.path);
        }
      })
      .catch(() => {});
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <aside className="panel panel--repo" aria-label="Repository">
      <div className="panel__head">
        <span className="label">Repository</span>
        {state.kind === "loaded" && (
          <span className="chip" title={state.repo.path}>
            {state.repo.project_type}
          </span>
        )}
      </div>

      <form
        className="repo-load"
        onSubmit={(e) => {
          e.preventDefault();
          void load(path);
        }}
      >
        <input
          className="repo-load__input"
          value={path}
          placeholder="/path/to/repository"
          aria-label="Repository path"
          onChange={(e) => setPath(e.target.value)}
        />
        <button
          className="repo-load__btn"
          type="submit"
          disabled={state.kind === "loading" || path.trim().length === 0}
        >
          {state.kind === "loading" ? "…" : "Load"}
        </button>
      </form>

      <div className="panel__body">
        {state.kind === "idle" && (
          <div className="empty">
            No repository loaded.
            <div className="empty__cta">Paste a local path above and load it.</div>
          </div>
        )}
        {state.kind === "error" && (
          <div className="empty empty--error">Could not load repository. {state.message}</div>
        )}
        {state.kind === "loaded" && (
          <>
            <div className="repo-meta" data-testid="repo-meta">
              <span className="repo-meta__name">{state.repo.name}</span>
              <span className="repo-meta__sub">
                {state.repo.file_count} files{state.repo.truncated ? " (truncated)" : ""}
              </span>
            </div>
            <ul className="tree" role="tree">
              {(state.tree.children ?? []).map((child) => (
                <TreeItem key={child.path} node={child} depth={0} />
              ))}
            </ul>
          </>
        )}
      </div>
    </aside>
  );
}

function TreeItem({ node, depth }: { node: TreeNode; depth: number }) {
  const [open, setOpen] = useState(depth < 1);
  const isDir = node.type === "dir";
  const pad = { paddingLeft: `${depth * 12 + 8}px` };

  if (!isDir) {
    return (
      <li className="tree-item" style={pad} role="treeitem" title={node.path}>
        <span className="tree-item__icon">◦</span>
        {node.name}
      </li>
    );
  }

  return (
    <li role="treeitem" aria-expanded={open}>
      <button className="tree-item tree-item--dir" style={pad} onClick={() => setOpen((o) => !o)}>
        <span className="tree-item__icon">{open ? "▾" : "▸"}</span>
        {node.name}
      </button>
      {open && (
        <ul className="tree" role="group">
          {(node.children ?? []).map((child) => (
            <TreeItem key={child.path} node={child} depth={depth + 1} />
          ))}
        </ul>
      )}
    </li>
  );
}
