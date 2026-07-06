"""Tests for the plan-first workflow (TASK 7)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import load_config
from app.main import create_app


def _client() -> TestClient:
    return TestClient(create_app(config=load_config(environ={})))


def test_plan_returns_structured_plan():
    """A change request returns a structured plan (SUBTASK 7.1)."""
    client = _client()
    resp = client.post("/api/plan", json={"message": "add a login form"})
    assert resp.status_code == 200
    plan = resp.json()["plan"]
    assert plan["goal"] == "add a login form"
    for field in ("steps", "risks", "tests"):
        assert isinstance(plan[field], list) and plan[field]
    assert plan["expected_output"]
    assert "files_to_change" in plan


def test_regenerating_replaces_pending_plan_and_resets_approval():
    """A new plan replaces the previous pending plan (SUBTASK 7.3)."""
    client = _client()
    client.post("/api/plan", json={"message": "first change"})
    client.post("/api/plan/approve")
    assert client.get("/api/plan").json()["approved"] is True

    client.post("/api/plan", json={"message": "second change"})
    state = client.get("/api/plan").json()
    assert state["plan"]["goal"] == "second change"  # replaced
    assert state["approved"] is False  # approval reset


def test_edit_blocked_without_approved_plan():
    """A direct edit without an approved plan returns a safe error (SUBTASK 7.4)."""
    client = _client()

    # No plan at all.
    resp = client.post("/api/edit")
    assert resp.status_code == 400
    assert "approved plan" in resp.json()["detail"].lower()

    # Plan exists but not approved.
    client.post("/api/plan", json={"message": "change"})
    assert client.post("/api/edit").status_code == 400

    # After approval, the edit gate opens.
    client.post("/api/plan/approve")
    ok = client.post("/api/edit")
    assert ok.status_code == 200
    assert ok.json()["ok"] is True


def test_approve_without_plan_errors():
    client = _client()
    resp = client.post("/api/plan/approve")
    assert resp.status_code == 400
    assert "no plan" in resp.json()["detail"].lower()


def test_plan_populates_files_when_repo_and_module(tmp_path):
    """When a repo is loaded and a module is given, files_to_change is populated."""
    from app.repo import SessionStore, load_repository

    repo = tmp_path / "proj"
    (repo / "checkout").mkdir(parents=True)
    (repo / "checkout" / "pay.py").write_text("def pay():\n    pass\n")
    (repo / "checkout" / "cart.py").write_text("def cart():\n    pass\n")

    app = create_app(config=load_config(environ={}))
    store = SessionStore(tmp_path / "state.json")
    metadata, _ = load_repository(str(repo), load_config(environ={}))
    store.save_repo(metadata)
    app.state.session_store = store
    client = TestClient(app)

    plan = client.post("/api/plan", json={"message": "fix checkout", "module": "checkout"}).json()[
        "plan"
    ]
    assert set(plan["files_to_change"]) == {"checkout/pay.py", "checkout/cart.py"}
