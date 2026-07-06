import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// Mock the backend client so tests are deterministic (no server needed).
vi.mock("./api", () => ({
  fetchHealth: vi.fn().mockResolvedValue({
    status: "ok",
    service: "hephaestus-backend",
    version: "0.1.0",
    ai_configured: false,
    config: {
      server: { host: "127.0.0.1", port: 8000 },
      ai_configured: false,
      ai_endpoint_set: false,
      model_tiers: { medium: "claude-sonnet-5" },
      default_tier: "medium",
      ignore_paths: [],
      context_max_tokens: 128000,
    },
  }),
  streamChat: vi.fn(async function* () {
    // Mock reply exercising markdown + a fenced code block (SUBTASK 2.4).
    const chunks = [
      "Here's my **plan**.\n\n",
      "```python\n",
      "def forge():\n    return 'hot'\n",
      "```\n",
    ];
    for (const c of chunks) yield c;
  }),
  fetchRepository: vi.fn().mockResolvedValue(null),
  loadRepository: vi.fn(),
  buildContext: vi.fn().mockResolvedValue({ file_count: 2, chunk_count: 3 }),
  generatePlan: vi.fn(),
  approvePlan: vi.fn().mockResolvedValue(undefined),
  tryEdit: vi.fn().mockResolvedValue({ ok: true, message: "ready to apply edits." }),
  revertEdits: vi.fn().mockResolvedValue([]),
  editStatus: vi.fn().mockResolvedValue([]),
}));

import { App } from "./App";
import { fetchRepository, generatePlan, loadRepository, streamChat } from "./api";
import type { Plan, RepoMetadata, TreeNode } from "./api";

const PLAN: Plan = {
  goal: "add login",
  files_to_change: ["backend/auth.py"],
  steps: ["Inspect files", "Draft change", "Run tests"],
  risks: ["May affect callers"],
  tests: ["pytest"],
  expected_output: "A reviewed change",
};

beforeEach(() => {
  vi.clearAllMocks();
});

const REPO_META: RepoMetadata = {
  path: "/proj",
  name: "proj",
  project_type: "mixed",
  file_count: 1,
  truncated: false,
  loaded_at: "x",
};
const REPO_TREE: TreeNode = {
  name: "proj",
  path: "",
  type: "dir",
  children: [
    { name: "backend", path: "backend", type: "dir", children: [] },
    { name: "frontend", path: "frontend", type: "dir", children: [] },
  ],
};

describe("Chat UI MVP", () => {
  it("renders the three panels without a repository (2.1)", async () => {
    render(<App />);
    // Left: repo tree empty state
    expect(screen.getByText(/no repository loaded/i)).toBeInTheDocument();
    // Center: chat welcome
    expect(screen.getByRole("heading", { name: /what shall we forge/i })).toBeInTheDocument();
    // Right: status panel
    expect(screen.getByLabelText(/task and status/i)).toBeInTheDocument();
    // Header connects to backend
    await waitFor(() => expect(screen.getByText(/backend v0\.1\.0/i)).toBeInTheDocument());
  });

  it("streams an assistant reply with a rendered code block (2.2 / 2.3 / 2.4)", async () => {
    const user = userEvent.setup();
    render(<App />);

    const box = screen.getByLabelText("Message");
    await user.type(box, "add a login form");
    await user.click(screen.getByLabelText("Send message"));

    // User message shows immediately.
    expect(screen.getByText("add a login form")).toBeInTheDocument();

    // Assistant reply streams in and renders markdown + a python code block.
    await waitFor(() => expect(screen.getByText(/here's my/i)).toBeInTheDocument());
    await waitFor(() => {
      expect(screen.getByText("python")).toBeInTheDocument(); // code language label
      expect(screen.getByText("copy")).toBeInTheDocument();
    });
  });

  it("action buttons trigger visible state changes (2.5)", async () => {
    const user = userEvent.setup();
    render(<App />);

    const statusPanel = screen.getByLabelText(/task and status/i);
    expect(screen.getByTestId("last-action")).toHaveTextContent("—");
    // Apply is disabled until a plan exists (SUBTASK 7.2).
    expect(within(statusPanel).getByRole("button", { name: /^apply$/i })).toBeDisabled();

    await user.click(within(statusPanel).getByRole("button", { name: /^test$/i }));
    expect(screen.getByTestId("last-action")).toHaveTextContent("Test");

    await user.click(within(statusPanel).getByRole("button", { name: /save context/i }));
    expect(screen.getByTestId("last-action")).toHaveTextContent("Save Context");
    expect(screen.getByTestId("last-action")).toHaveTextContent(/1 context/i);
  });

  it("Plan generates a plan and enables Apply; Apply passes the edit guard (7.1/7.2/7.4)", async () => {
    vi.mocked(generatePlan).mockResolvedValue(PLAN);
    const user = userEvent.setup();
    render(<App />);
    const statusPanel = screen.getByLabelText(/task and status/i);
    const applyBtn = () => within(statusPanel).getByRole("button", { name: /^apply$/i });
    expect(applyBtn()).toBeDisabled();

    // A message gives Plan something to target.
    await user.type(screen.getByLabelText("Message"), "add login");
    await user.click(screen.getByLabelText("Send message"));
    await waitFor(() => expect(screen.getByText("add login")).toBeInTheDocument());

    await user.click(within(statusPanel).getByRole("button", { name: /plan/i }));
    // Plan renders and Apply becomes enabled (SUBTASK 7.1 / 7.2).
    await waitFor(() => expect(applyBtn()).not.toBeDisabled());
    expect(screen.getByText(/files likely to change/i)).toBeInTheDocument();

    await user.click(applyBtn());
    await waitFor(() =>
      expect(screen.getByText(/ready to apply edits/i)).toBeInTheDocument()
    );
    expect(generatePlan).toHaveBeenCalledWith("add login", null);
  });

  it("sets and clears module focus via chat commands (6.2 / 6.4)", async () => {
    vi.mocked(fetchRepository).mockResolvedValue(REPO_META);
    vi.mocked(loadRepository).mockResolvedValue({ metadata: REPO_META, tree: REPO_TREE });
    const user = userEvent.setup();
    render(<App />);
    await screen.findByTestId("repo-meta"); // repo restored/loaded

    const box = screen.getByLabelText("Message");
    await user.type(box, "focus on backend");
    await user.click(screen.getByLabelText("Send message"));

    // Focus chip appears; the assistant confirms locally (no AI call).
    expect(await screen.findByTestId("focus-chip")).toHaveTextContent("backend");
    expect(screen.getByText(/focused on module/i)).toBeInTheDocument();
    expect(streamChat).not.toHaveBeenCalled();

    // Clearing focus removes the chip.
    await user.type(box, "clear focus");
    await user.click(screen.getByLabelText("Send message"));
    await waitFor(() => expect(screen.queryByTestId("focus-chip")).not.toBeInTheDocument());
  });
});
