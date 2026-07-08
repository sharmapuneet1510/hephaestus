import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { TasksState } from "../api";

vi.mock("../api", () => ({ fetchTasks: vi.fn(), runSubtask: vi.fn() }));

import { fetchTasks, runSubtask } from "../api";
import { TasksPanel } from "./TasksPanel";

const STATE: TasksState = {
  tasks: [
    {
      id: "T1",
      title: "Bootstrap",
      progress: 40,
      status: "pending",
      subtasks: [{ id: "T1.1", title: "Base structure", status: "pending" }],
    },
  ],
  overall_progress: 0,
};

const DONE: TasksState = {
  tasks: [
    {
      id: "T1",
      title: "Bootstrap",
      progress: 40,
      status: "done",
      subtasks: [{ id: "T1.1", title: "Base structure", status: "done" }],
    },
  ],
  overall_progress: 40,
};

beforeEach(() => vi.clearAllMocks());

describe("TasksPanel (TASK 10)", () => {
  it("displays tasks and subtasks (10.2)", async () => {
    vi.mocked(fetchTasks).mockResolvedValue(STATE);
    render(<TasksPanel />);
    expect(await screen.findByText("Bootstrap")).toBeInTheDocument();
    expect(screen.getByText("Base structure")).toBeInTheDocument();
    expect(screen.getByTestId("overall-progress")).toHaveTextContent("0%");
  });

  it("runs a subtask and updates overall progress (10.3 / 10.4)", async () => {
    vi.mocked(fetchTasks).mockResolvedValueOnce(STATE).mockResolvedValue(DONE);
    vi.mocked(runSubtask).mockResolvedValue({
      task: DONE.tasks[0],
      subtask: DONE.tasks[0].subtasks[0],
      overall_progress: 40,
    });
    const user = userEvent.setup();
    render(<TasksPanel />);

    await screen.findByText("Bootstrap");
    await user.click(screen.getByRole("button", { name: /run/i }));

    expect(runSubtask).toHaveBeenCalledWith("T1", "T1.1");
    await waitFor(() =>
      expect(screen.getByTestId("overall-progress")).toHaveTextContent("40%")
    );
  });
});
