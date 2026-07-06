"""Tests for the test runner (TASK 9)."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import load_config
from app.main import create_app
from app.repo import SessionStore, load_repository
from app.testrunner import TestResult, detect_test_command, run_command


def _config():
    return load_config(environ={})


# --------------------------------------------------------------------------- #
# 9.1 — Detection
# --------------------------------------------------------------------------- #
def test_detect_test_command_per_project(tmp_path):
    node = tmp_path / "node"
    node.mkdir()
    (node / "package.json").write_text("{}")
    assert detect_test_command(node, _config()) == "npm test"

    py = tmp_path / "py"
    py.mkdir()
    (py / "pyproject.toml").write_text("")
    assert detect_test_command(py, _config()) == "pytest"

    mvn = tmp_path / "mvn"
    mvn.mkdir()
    (mvn / "pom.xml").write_text("")
    assert detect_test_command(mvn, _config()) == "mvn test"

    gradle = tmp_path / "gr"
    gradle.mkdir()
    (gradle / "build.gradle").write_text("")
    assert detect_test_command(gradle, _config()) == "gradle test"

    empty = tmp_path / "empty"
    empty.mkdir()
    assert detect_test_command(empty, _config()) is None


# --------------------------------------------------------------------------- #
# 9.2 / 9.3 — Execution + summary
# --------------------------------------------------------------------------- #
def test_run_command_captures_passing(tmp_path):
    cmd = f"{sys.executable} -c \"print('1 passed')\""
    result = run_command(cmd, tmp_path)
    assert result.passed is True
    assert result.exit_code == 0
    assert "1 passed" in result.output
    assert result.duration_ms >= 0


def test_run_command_captures_failing_with_summary(tmp_path):
    cmd = (
        f"{sys.executable} -c "
        "\"import sys; print('FAILED tests/test_x.py::test_it'); "
        "print('1 failed, 2 passed'); sys.exit(1)\""
    )
    result = run_command(cmd, tmp_path)
    assert result.passed is False
    assert result.exit_code == 1
    assert "1 failed" in result.summary  # SUBTASK 9.3
    assert "tests/test_x.py" in result.failed_files


def test_run_command_missing_binary(tmp_path):
    result = run_command("definitely-not-a-real-binary-xyz --run", tmp_path)
    assert result.exit_code == 127
    assert "not found" in result.summary.lower()


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #
def _client(tmp_path: Path, repo: Path) -> TestClient:
    app = create_app(config=_config())
    store = SessionStore(tmp_path / "state.json")
    metadata, _ = load_repository(str(repo), _config())
    store.save_repo(metadata)
    app.state.session_store = store
    return TestClient(app)


def test_detect_endpoint(tmp_path):
    repo = tmp_path / "proj"
    repo.mkdir()
    (repo / "package.json").write_text("{}")
    client = _client(tmp_path, repo)
    assert client.get("/api/test/detect").json()["command"] == "npm test"


def test_run_endpoint_rejects_arbitrary_command(tmp_path):
    repo = tmp_path / "proj"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("")
    client = _client(tmp_path, repo)
    resp = client.post("/api/test", json={"command": "rm -rf /"})
    assert resp.status_code == 400
    assert "not allowed" in resp.json()["detail"].lower()


# --------------------------------------------------------------------------- #
# 9.4 — Failures fed into the next plan
# --------------------------------------------------------------------------- #
def test_failing_tests_included_in_next_plan(tmp_path):
    repo = tmp_path / "proj"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("")

    app = create_app(config=_config())
    store = SessionStore(tmp_path / "state.json")
    metadata, _ = load_repository(str(repo), _config())
    store.save_repo(metadata)
    app.state.session_store = store
    # Simulate a prior failing run (SUBTASK 9.4).
    app.state.test_state.last = TestResult(
        command="pytest",
        exit_code=1,
        passed=False,
        duration_ms=10,
        summary="1 failed, 2 passed",
        output="FAILED tests/test_x.py::test_it",
        failed_files=["tests/test_x.py"],
    )
    client = TestClient(app)

    plan = client.post("/api/plan", json={"message": "fix the bug"}).json()["plan"]
    assert plan["failing_tests"] == "1 failed, 2 passed"
    assert any("failing tests" in step.lower() for step in plan["steps"])
