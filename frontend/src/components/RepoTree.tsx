// Left panel — repository tree. Loading a real repo lands in TASK 4; for now
// this renders a clear empty state (SUBTASK 2.1: UI renders without a repo).

export function RepoTree() {
  return (
    <aside className="panel panel--repo" aria-label="Repository">
      <div className="panel__head">
        <span className="label">Repository</span>
      </div>
      <div className="panel__body">
        <div className="empty">
          No repository loaded.
          <div className="empty__cta">Load a repo to begin (coming in TASK 4)</div>
        </div>
      </div>
    </aside>
  );
}
