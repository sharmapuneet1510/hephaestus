"""Tests for the final documentation generator (TASK 14)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import load_config
from app.docs import agent_workflow_guide, setup_guide, usage_guide
from app.main import create_app


def _client() -> TestClient:
    return TestClient(create_app(config=load_config(environ={})))


def test_setup_guide_has_install_config_run():
    md = setup_guide().lower()
    assert "install" in md and "config" in md and "run" in md
    assert "uv pip install" in md and "npm install" in md and "uvicorn" in md


def test_usage_guide_covers_workflow():
    md = usage_guide().lower()
    for word in ("load", "chat", "focus", "plan", "apply", "test"):
        assert word in md


def test_agent_workflow_guide_has_lifecycle():
    md = agent_workflow_guide().lower()
    for word in ("task", "subtask", "claude.md", "test", "lifecycle"):
        assert word in md


def test_architecture_reflects_actual_routes():
    """The architecture doc reflects mounted modules + real endpoints (14.3)."""
    md = _client().get("/api/docs", params={"kind": "architecture"}).json()["content"]
    assert "## Modules" in md
    # Live endpoints from the actual app.
    assert "POST /api/chat" in md
    assert "POST /api/plan" in md
    assert "POST /api/edit/apply" in md


def test_docs_endpoint_kinds():
    client = _client()
    for kind in ("setup", "usage", "architecture", "agent"):
        resp = client.get("/api/docs", params={"kind": kind})
        assert resp.status_code == 200 and resp.json()["content"]

    all_docs = client.get("/api/docs", params={"kind": "all"}).json()["content"]
    assert "Setup Guide" in all_docs and "Architecture Summary" in all_docs

    assert client.get("/api/docs", params={"kind": "bogus"}).status_code == 400
