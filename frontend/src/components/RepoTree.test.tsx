import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { RepoMetadata, TreeNode } from "../api";

vi.mock("../api", () => ({
  fetchRepository: vi.fn(),
  loadRepository: vi.fn(),
}));

import { fetchRepository, loadRepository } from "../api";
import { RepoTree } from "./RepoTree";

const META: RepoMetadata = {
  path: "/repo/sample",
  name: "sample",
  project_type: "node",
  file_count: 4,
  truncated: false,
  loaded_at: "2026-07-06T00:00:00Z",
};

const TREE: TreeNode = {
  name: "sample",
  path: "",
  type: "dir",
  children: [
    { name: "src", path: "src", type: "dir", children: [{ name: "index.js", path: "src/index.js", type: "file" }] },
    { name: "package.json", path: "package.json", type: "file" },
  ],
};

beforeEach(() => vi.clearAllMocks());

describe("RepoTree (TASK 4)", () => {
  it("shows the empty state when no repo is loaded (4.1)", async () => {
    vi.mocked(fetchRepository).mockResolvedValue(null);
    render(<RepoTree />);
    expect(await screen.findByText(/no repository loaded/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/repository path/i)).toBeInTheDocument();
  });

  it("loads a repo and renders its tree + project type (4.1 / 4.2 / 4.4)", async () => {
    vi.mocked(fetchRepository).mockResolvedValue(null);
    vi.mocked(loadRepository).mockResolvedValue({ metadata: META, tree: TREE });
    const user = userEvent.setup();
    render(<RepoTree />);

    await user.type(screen.getByLabelText(/repository path/i), "/repo/sample");
    await user.click(screen.getByRole("button", { name: /load/i }));

    // Repo name + project-type chip + tree nodes appear.
    await waitFor(() => expect(screen.getByTestId("repo-meta")).toHaveTextContent("sample"));
    expect(screen.getByText("node")).toBeInTheDocument();
    expect(screen.getByText("src")).toBeInTheDocument();
    expect(screen.getByText("package.json")).toBeInTheDocument();
    expect(loadRepository).toHaveBeenCalledWith("/repo/sample");
  });

  it("restores the last-loaded repo on mount (4.5)", async () => {
    vi.mocked(fetchRepository).mockResolvedValue(META);
    vi.mocked(loadRepository).mockResolvedValue({ metadata: META, tree: TREE });
    render(<RepoTree />);

    // Without any user action, the stored path is reloaded.
    await waitFor(() => expect(loadRepository).toHaveBeenCalledWith("/repo/sample"));
    expect(await screen.findByTestId("repo-meta")).toHaveTextContent("sample");
  });

  it("shows a safe error when the path is invalid (4.1)", async () => {
    vi.mocked(fetchRepository).mockResolvedValue(null);
    vi.mocked(loadRepository).mockRejectedValue(new Error("Path does not exist: /nope"));
    const user = userEvent.setup();
    render(<RepoTree />);

    await user.type(screen.getByLabelText(/repository path/i), "/nope");
    await user.click(screen.getByRole("button", { name: /load/i }));

    expect(await screen.findByText(/could not load repository/i)).toBeInTheDocument();
    expect(screen.getByText(/path does not exist/i)).toBeInTheDocument();
  });
});
