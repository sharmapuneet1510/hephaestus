"""MVP end-to-end validation (TASK 15).

Drives the whole stack through the real endpoints — load → context → plan →
apply → test → CLAUDE.md (15.1), failure recovery (15.2), large-repo chunking /
compact context (15.3), and final-docs accuracy (15.4).
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import load_config
from app.context import chunk_content
from app.main import create_app
from app.repo import SessionStore, load_repository

# Harmless test commands (deterministic, cross-platform via sys.executable).
_PASS = sys.executable + " -c \"print('1 passed')\""
_FAIL = sys.executable + " -c \"import sys; print('1 failed, 0 passed'); sys.exit(1)\""


def _app_with_repo(tmp_path: Path, repo: Path, config) -> TestClient:
    app = create_app(config=config)
    store = SessionStore(tmp_path / "state.json")
    metadata, _ = load_repository(str(repo), config)
    store.save_repo(metadata)
    app.state.session_store = store
    return TestClient(app)


def test_full_user_journey(tmp_path):
    """load -> context -> plan -> apply -> test -> CLAUDE.md, end to end (15.1)."""
    config = load_config(environ={})
    config.test_commands["python"] = _PASS  # harmless passing test

    repo = tmp_path / "proj"
    (repo / "src").mkdir(parents=True)
    (repo / "pyproject.toml").write_text("")
    (repo / "src" / "app.py").write_text("def add(a, b):\n    return a + b\n")
    client = _app_with_repo(tmp_path, repo, config)

    # Context for the module.
    ctx = client.post("/api/context/build", json={"format": "toon", "focus": "src"}).json()
    assert ctx["file_count"] >= 1

    # Plan-first.
    plan = client.post(
        "/api/plan", json={"message": "add a subtract function", "module": "src"}
    ).json()["plan"]
    assert plan["goal"] and plan["steps"]

    # Approve + apply an edit.
    assert client.post("/api/plan/approve").status_code == 200
    apply = client.post(
        "/api/edit/apply",
        json={
            "path": "src/app.py",
            "new_content": "def add(a, b):\n    return a + b\n\n\ndef sub(a, b):\n    return a - b\n",
        },
    ).json()
    assert "def sub" in (repo / "src" / "app.py").read_text()
    assert "+def sub(a, b):" in apply["diff"]

    # Run tests (passes).
    result = client.post("/api/test", json={}).json()
    assert result["passed"] is True

    # Record to CLAUDE.md.
    note = client.post("/api/knowledge/note", json={"note": "Added subtract function"}).json()
    assert note["added"] is True
    assert (repo / "CLAUDE.md").is_file()
    assert "Added subtract function" in (repo / "CLAUDE.md").read_text()


def test_failure_recovery(tmp_path):
    """A failing test produces a fix plan and a retry can proceed (15.2)."""
    config = load_config(environ={})
    config.test_commands["python"] = _FAIL

    repo = tmp_path / "proj"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("")
    (repo / "mod.py").write_text("def f():\n    return 0\n")
    client = _app_with_repo(tmp_path, repo, config)

    # Test fails.
    result = client.post("/api/test", json={}).json()
    assert result["passed"] is False
    assert "failed" in result["summary"].lower()

    # The next plan folds in the failure (fix plan).
    plan = client.post("/api/plan", json={"message": "fix the bug"}).json()["plan"]
    assert plan["failing_tests"] and "failed" in plan["failing_tests"].lower()
    assert any("failing tests" in step.lower() for step in plan["steps"])

    # Retry: approve + apply is allowed after the fix plan.
    client.post("/api/plan/approve")
    apply = client.post(
        "/api/edit/apply", json={"path": "mod.py", "new_content": "def f():\n    return 1\n"}
    )
    assert apply.status_code == 200


def test_large_repo_chunking_and_compact_context(tmp_path):
    """A large repo chunks files and keeps prompt context compact (15.3)."""
    config = load_config(environ={})
    repo = tmp_path / "big"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("")
    big = "\n".join(f"x{i} = {i}" for i in range(2000))
    (repo / "big.py").write_text(big)

    # A large file is split into line-aware chunks (not loaded as one blob).
    chunks = chunk_content("big.py", big, config.context.chunk_size_lines)
    assert len(chunks) == 5  # 2000 lines / 400

    # The built context is compact metadata — far smaller than the raw source.
    client = _app_with_repo(tmp_path, repo, config)
    toon = client.post("/api/context/build", json={"format": "toon"}).json()["content"]
    assert len(toon) < len(big) / 10  # not a blind full load


def test_final_docs_match_app(tmp_path):
    """Generated docs reflect the actual app behavior and config (15.4)."""
    config = load_config(environ={})
    client = TestClient(create_app(config=config))

    all_docs = client.get("/api/docs", params={"kind": "all"}).json()["content"]
    assert "Setup Guide" in all_docs and "Usage Guide" in all_docs
    assert "Architecture Summary" in all_docs and "Agent Workflow Guide" in all_docs
    # Reflects real endpoints and the actual config file.
    assert "POST /api/edit/apply" in all_docs
    assert "POST /api/plan" in all_docs
    assert "config/default.yaml" in all_docs
