"""Tests for CLAUDE.md knowledge maintenance (TASK 11)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.config import load_config
from app.knowledge import add_note, build_prompt_preamble, ensure, template
from app.main import create_app
from app.repo import SessionStore, load_repository


def _config():
    return load_config(environ={})


def test_template_has_required_sections():
    md = template("demo")
    for section in ("Project Overview", "Test Commands", "Completed Task Notes", "Known Issues"):
        assert f"## {section}" in md


def test_ensure_creates_when_missing(tmp_path):
    """CLAUDE.md is generated with required sections when missing (SUBTASK 11.1)."""
    created, content = ensure(tmp_path, _config())
    assert created is True
    assert (tmp_path / "CLAUDE.md").is_file()
    assert "## Completed Task Notes" in content

    # Already exists -> not recreated.
    again, _ = ensure(tmp_path, _config())
    assert again is False


def test_add_note_appends_under_section(tmp_path):
    """A completed-task note is added under its section (SUBTASK 11.2)."""
    added, content = add_note(tmp_path, _config(), "Implemented login form")
    assert added is True
    assert "- Implemented login form" in content
    # It lands under the Completed Task Notes section.
    body = content.split("## Completed Task Notes", 1)[1]
    assert "- Implemented login form" in body


def test_add_note_dedupes(tmp_path):
    """The same note is not duplicated (SUBTASK 11.3)."""
    add_note(tmp_path, _config(), "Ran the test suite")
    added, content = add_note(tmp_path, _config(), "Ran the test suite")
    assert added is False
    assert content.count("- Ran the test suite") == 1


def test_add_note_custom_section(tmp_path):
    added, content = add_note(
        tmp_path, _config(), "Use 2-space indent", section="Coding Conventions"
    )
    assert added is True
    body = content.split("## Coding Conventions", 1)[1].split("##", 1)[0]
    assert "- Use 2-space indent" in body


def test_build_prompt_preamble_includes_knowledge(tmp_path):
    """The prompt builder includes stored conventions (SUBTASK 11.4)."""
    add_note(
        tmp_path, _config(), "Always prefer composition over inheritance", "Coding Conventions"
    )
    preamble = build_prompt_preamble(tmp_path, _config())
    assert "CLAUDE.md" in preamble
    assert "prefer composition over inheritance" in preamble

    # No file -> empty preamble.
    assert build_prompt_preamble(tmp_path / "elsewhere", _config()) == ""


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


def test_knowledge_endpoints(tmp_path):
    repo = tmp_path / "proj"
    repo.mkdir()
    client = _client(tmp_path, repo)

    assert client.get("/api/knowledge").json()["exists"] is False

    ensured = client.post("/api/knowledge/ensure").json()
    assert ensured["created"] is True

    noted = client.post("/api/knowledge/note", json={"note": "Wired auth module"}).json()
    assert noted["added"] is True
    assert "- Wired auth module" in noted["content"]

    got = client.get("/api/knowledge").json()
    assert got["exists"] is True and "Wired auth module" in got["content"]
