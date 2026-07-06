"""Tests for file editing and diff review (TASK 8)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.config import load_config
from app.main import create_app
from app.repo import SessionStore, load_repository


def _client(tmp_path: Path) -> tuple[TestClient, Path]:
    repo = tmp_path / "proj"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "a.txt").write_text("line 1\nline 2\nline 3\n")
    (repo / "src" / "b.txt").write_text("untouched\n")

    app = create_app(config=load_config(environ={}))
    store = SessionStore(tmp_path / "state.json")
    metadata, _ = load_repository(str(repo), load_config(environ={}))
    store.save_repo(metadata)
    app.state.session_store = store
    return TestClient(app), repo


def _approve_plan(client: TestClient) -> None:
    client.post("/api/plan", json={"message": "edit a.txt"})
    client.post("/api/plan/approve")


def test_read_blocks_paths_outside_workspace(tmp_path):
    """Reading outside the loaded repo is blocked (SUBTASK 8.1)."""
    client, _ = _client(tmp_path)
    assert client.get("/api/file", params={"path": "src/a.txt"}).status_code == 200
    resp = client.get("/api/file", params={"path": "../../etc/passwd"})
    assert resp.status_code == 400
    assert "outside the workspace" in resp.json()["detail"].lower()


def test_apply_changes_only_target_file(tmp_path):
    """Applying a patch changes only the targeted file (SUBTASK 8.2)."""
    client, repo = _client(tmp_path)
    _approve_plan(client)

    resp = client.post(
        "/api/edit/apply",
        json={"path": "src/a.txt", "new_content": "line 1\nline TWO\nline 3\n"},
    )
    assert resp.status_code == 200
    assert (repo / "src" / "a.txt").read_text() == "line 1\nline TWO\nline 3\n"
    assert (repo / "src" / "b.txt").read_text() == "untouched\n"  # unchanged


def test_apply_blocked_without_approved_plan(tmp_path):
    """Editing without an approved plan is refused (plan-first, SUBTASK 7.4)."""
    client, _ = _client(tmp_path)
    resp = client.post("/api/edit/apply", json={"path": "src/a.txt", "new_content": "x"})
    assert resp.status_code == 400
    assert "approved plan" in resp.json()["detail"].lower()


def test_diff_shows_changed_lines(tmp_path):
    """The diff accurately shows added/removed lines (SUBTASK 8.3)."""
    client, _ = _client(tmp_path)
    diff = client.post(
        "/api/edit/preview",
        json={"path": "src/a.txt", "new_content": "line 1\nline TWO\nline 3\n"},
    ).json()["diff"]
    assert "-line 2\n" in diff
    assert "+line TWO\n" in diff


def test_revert_restores_original_content(tmp_path):
    """Revert restores the original file content (SUBTASK 8.4)."""
    client, repo = _client(tmp_path)
    _approve_plan(client)
    original = (repo / "src" / "a.txt").read_text()

    client.post("/api/edit/apply", json={"path": "src/a.txt", "new_content": "changed\n"})
    assert (repo / "src" / "a.txt").read_text() == "changed\n"

    reverted = client.post("/api/edit/revert").json()["reverted"]
    assert reverted == ["src/a.txt"]
    assert (repo / "src" / "a.txt").read_text() == original


def test_revert_removes_created_file(tmp_path):
    client, repo = _client(tmp_path)
    _approve_plan(client)
    client.post("/api/edit/apply", json={"path": "src/new.txt", "new_content": "hi\n"})
    assert (repo / "src" / "new.txt").is_file()

    client.post("/api/edit/revert")
    assert not (repo / "src" / "new.txt").exists()  # created file removed


def test_status_tracks_touched_files(tmp_path):
    """The touched-files list updates after edits (SUBTASK 8.5)."""
    client, _ = _client(tmp_path)
    _approve_plan(client)
    assert client.get("/api/edit/status").json()["files"] == []

    client.post("/api/edit/apply", json={"path": "src/a.txt", "new_content": "x\n"})
    client.post("/api/edit/apply", json={"path": "src/b.txt", "new_content": "y\n"})
    assert client.get("/api/edit/status").json()["files"] == ["src/a.txt", "src/b.txt"]

    client.post("/api/edit/revert")
    assert client.get("/api/edit/status").json()["files"] == []
