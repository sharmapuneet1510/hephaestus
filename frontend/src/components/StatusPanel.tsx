import type { WorkspaceStatus } from "../types";

export type ActionKind = "plan" | "apply" | "test" | "revert" | "save";

const TEST_LABELS: Record<WorkspaceStatus["testStatus"], string> = {
  idle: "no tests run",
  running: "running…",
  passed: "passed",
  failed: "failed",
};

export function StatusPanel({
  status,
  busy,
  onAction,
}: {
  status: WorkspaceStatus;
  busy: boolean;
  onAction: (action: ActionKind) => void;
}) {
  return (
    <aside className="panel panel--status" aria-label="Task and status">
      <div className="panel__head">
        <span className="label">Task &amp; Status</span>
      </div>

      <div className="panel__body">
        <div className="status-block">
          <div className="status-block__label">Current Task</div>
          <div className="status-value">{status.currentTask}</div>
        </div>

        <div className="status-block">
          <div className="status-block__label">Module Focus</div>
          {status.moduleFocus ? (
            <span className="chip chip--focus">◎ {status.moduleFocus}</span>
          ) : (
            <span className="status-value status-value--muted">none</span>
          )}
        </div>

        <div className="status-block">
          <div className="status-block__label">Tests</div>
          <span className={`test-badge test-badge--${status.testStatus}`}>
            {TEST_LABELS[status.testStatus]}
          </span>
        </div>

        <div className="status-block">
          <div className="status-block__label">
            Files Touched ({status.filesTouched.length})
          </div>
          {status.filesTouched.length === 0 ? (
            <span className="status-value status-value--muted">none yet</span>
          ) : (
            status.filesTouched.map((f) => (
              <div className="file-row" key={f}>
                {f}
              </div>
            ))
          )}
        </div>

        <div className="status-block">
          <div className="status-block__label">Last Action</div>
          <div className="status-value" data-testid="last-action">
            {status.lastAction ?? "—"}
            {status.savedContexts > 0 && (
              <span className="status-value--muted"> · {status.savedContexts} context(s) saved</span>
            )}
          </div>
        </div>
      </div>

      <div className="actions">
        <button
          className="action action--primary"
          type="button"
          disabled={busy}
          onClick={() => onAction("plan")}
        >
          ⬒ Plan
        </button>
        <button className="action" type="button" disabled={busy} onClick={() => onAction("apply")}>
          Apply
        </button>
        <button className="action" type="button" disabled={busy} onClick={() => onAction("test")}>
          Test
        </button>
        <button
          className="action action--danger"
          type="button"
          disabled={busy}
          onClick={() => onAction("revert")}
        >
          Revert
        </button>
        <button className="action" type="button" disabled={busy} onClick={() => onAction("save")}>
          Save Context
        </button>
      </div>
    </aside>
  );
}
