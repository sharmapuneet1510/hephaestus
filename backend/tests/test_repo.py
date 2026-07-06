"""Tests for the repository loader (TASK 4)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import load_config
from app.main import create_app
from app.repo import (
    RepoError,
    SessionStore,
    build_tree,
    detect_project_type,
    load_repository,
)


def _make_repo(tmp_path: Path) -> Path:
    """A small sample repo exercising ignore rules and project detection."""
    repo = tmp_path / "sample"
    (repo / "src").mkdir(parents=True)
    (repo / "node_modules" / "dep").mkdir(parents=True)
    (repo / ".git").mkdir()
    (repo / "build").mkdir()

    (repo / "package.json").write_text('{"name":"sample"}')
    (repo / "README.md").write_text("# sample")
    (repo / "src" / "index.js").write_text("console.log('hi')")
    (repo / "node_modules" / "dep" / "x.js").write_text("//dep")
    (repo / ".git" / "config").write_text("[core]")
    (repo / "build" / "out.txt").write_text("built")
    (repo / "app.log").write_text("log")
    (repo / ".gitignore").write_text("*.log\nbuild/\n")
    return repo


def _config():
    return load_config(environ={})


def _names(node) -> set[str]:
    """Flatten every node name in a tree."""
    out = {node.name} if node.path else set()
    for child in node.children or []:
        out |= _names(child)
    return out


def test_scan_applies_ignore_rules(tmp_path):
    repo = _make_repo(tmp_path)
    tree, file_count, truncated = build_tree(repo, _config())
    names = _names(tree)

    # Config ignore_paths + .gitignore exclusions (SUBTASK 4.3)
    assert "node_modules" not in names
    assert ".git" not in names
    assert "build" not in names  # from .gitignore "build/"
    assert "app.log" not in names  # from .gitignore "*.log"

    # Real files remain
    assert {"src", "index.js", "package.json", "README.md"} <= names
    assert file_count == 4  # index.js, package.json, README.md, .gitignore
    assert truncated is False


def test_tree_is_nested_and_sorted(tmp_path):
    repo = _make_repo(tmp_path)
    tree, _, _ = build_tree(repo, _config())
    top = tree.children
    # Directories sort before files.
    assert top[0].type == "dir" and top[0].name == "src"
    src = next(c for c in top if c.name == "src")
    assert src.children[0].name == "index.js"


@pytest.mark.parametrize(
    "markers,expected",
    [
        (["pom.xml"], "java"),
        (["package.json"], "node"),
        (["pyproject.toml"], "python"),
        (["go.mod"], "go"),
        (["package.json", "pom.xml"], "mixed"),
        ([], "unknown"),
    ],
)
def test_detect_project_type(tmp_path, markers, expected):
    repo = tmp_path / "p"
    repo.mkdir()
    for m in markers:
        (repo / m).write_text("x")
    assert detect_project_type(repo) == expected


def test_detect_project_type_monorepo(tmp_path):
    """Markers in subdirectories (backend/frontend) resolve to 'mixed'."""
    repo = tmp_path / "mono"
    (repo / "backend").mkdir(parents=True)
    (repo / "frontend").mkdir(parents=True)
    (repo / "backend" / "pyproject.toml").write_text("x")
    (repo / "frontend" / "package.json").write_text("x")
    assert detect_project_type(repo) == "mixed"


def test_load_repository_metadata(tmp_path):
    repo = _make_repo(tmp_path)
    metadata, tree = load_repository(str(repo), _config())
    assert metadata.name == "sample"
    assert metadata.project_type == "node"
    assert metadata.file_count == 4
    assert metadata.path == str(repo.resolve())
    assert tree.type == "dir"


def test_load_repository_rejects_missing_and_file(tmp_path):
    with pytest.raises(RepoError, match="does not exist"):
        load_repository(str(tmp_path / "nope"), _config())

    afile = tmp_path / "f.txt"
    afile.write_text("x")
    with pytest.raises(RepoError, match="Not a directory"):
        load_repository(str(afile), _config())


def test_session_store_roundtrip(tmp_path):
    store = SessionStore(tmp_path / ".hephaestus" / "session.json")
    assert store.load_repo() is None

    repo = _make_repo(tmp_path)
    metadata, _ = load_repository(str(repo), _config())
    store.save_repo(metadata)

    restored = store.load_repo()
    assert restored is not None
    assert restored.name == "sample"
    assert restored.project_type == "node"


# --------------------------------------------------------------------------- #
# Endpoint tests
# --------------------------------------------------------------------------- #
def _client(tmp_path: Path) -> TestClient:
    app = create_app(config=_config())
    app.state.session_store = SessionStore(tmp_path / "state" / "session.json")
    return TestClient(app)


def test_load_endpoint_returns_metadata_and_tree(tmp_path):
    repo = _make_repo(tmp_path)
    client = _client(tmp_path)
    resp = client.post("/api/repo/load", json={"path": str(repo)})
    assert resp.status_code == 200
    body = resp.json()
    assert body["metadata"]["project_type"] == "node"
    assert body["tree"]["type"] == "dir"
    names = {c["name"] for c in body["tree"]["children"]}
    assert "node_modules" not in names and "src" in names


def test_load_endpoint_rejects_bad_path(tmp_path):
    client = _client(tmp_path)
    resp = client.post("/api/repo/load", json={"path": str(tmp_path / "missing")})
    assert resp.status_code == 400
    assert "does not exist" in resp.json()["detail"]


def test_get_repo_restores_last_loaded(tmp_path):
    repo = _make_repo(tmp_path)
    client = _client(tmp_path)
    assert client.get("/api/repo").json()["metadata"] is None  # nothing yet

    client.post("/api/repo/load", json={"path": str(repo)})
    restored = client.get("/api/repo").json()["metadata"]
    assert restored is not None
    assert restored["name"] == "sample"
