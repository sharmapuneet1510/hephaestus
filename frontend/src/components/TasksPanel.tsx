import { useEffect, useState } from "react";
import { fetchTasks, runSubtask, type TasksState } from "../api";

// Agent task list with per-subtask run + overall MVP progress (TASK 10).

export function TasksPanel() {
  const [state, setState] = useState<TasksState | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = () => {
    fetchTasks()
      .then(setState)
      .catch(() => {});
  };

  useEffect(load, []);

  const run = async (taskId: string, subtaskId: string) => {
    setBusy(subtaskId);
    try {
      await runSubtask(taskId, subtaskId);
      load();
    } catch {
      /* ignore */
    } finally {
      setBusy(null);
    }
  };

  if (!state || state.tasks.length === 0) {
    return <div className="status-value status-value--muted">No task file loaded.</div>;
  }

  return (
    <div className="tasks">
      <div className="tasks__head">
        <span className="status-block__label">Tasks</span>
        <span className="tasks__pct" data-testid="overall-progress">
          {state.overall_progress}%
        </span>
      </div>
      <div className="progress" role="progressbar" aria-valuenow={state.overall_progress}>
        <div className="progress__bar" style={{ width: `${state.overall_progress}%` }} />
      </div>

      {state.tasks.map((task) => (
        <div className="task" key={task.id}>
          <div className="task__title">
            {task.title}
            <span className={`task__status task__status--${task.status}`}>{task.status}</span>
          </div>
          {task.subtasks.map((sub) => (
            <div className="subtask" key={sub.id}>
              <span className={`subtask__dot subtask__dot--${sub.status}`} aria-hidden="true" />
              <span className="subtask__title" title={sub.output ?? undefined}>
                {sub.title}
              </span>
              {sub.status !== "done" && (
                <button
                  className="subtask__run"
                  type="button"
                  disabled={busy === sub.id}
                  onClick={() => run(task.id, sub.id)}
                >
                  {busy === sub.id ? "…" : "Run"}
                </button>
              )}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
