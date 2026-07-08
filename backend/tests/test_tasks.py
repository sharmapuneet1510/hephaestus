"""Tests for agent task execution (TASK 10)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import load_config
from app.main import create_app
from app.tasks import TaskStore, overall_progress, parse_task_file

EXAMPLE = """
tasks:
  - id: T1
    title: Bootstrap
    progress: 40
    subtasks:
      - id: T1.1
        title: Base structure
        output: skeleton
      - id: T1.2
        title: Config files
  - id: T2
    title: Chat UI
    progress: 60
    subtasks:
      - id: T2.1
        title: Layout
"""


def _client() -> TestClient:
    return TestClient(create_app(config=load_config(environ={})))


def test_parse_task_file_validates(tmp_path):
    """An example task file parses and validates against the schema (SUBTASK 10.1)."""
    tf = parse_task_file(EXAMPLE, "yaml")
    assert [t.id for t in tf.tasks] == ["T1", "T2"]
    assert tf.tasks[0].subtasks[0].id == "T1.1"
    assert tf.tasks[0].subtasks[0].status == "pending"


def test_bundled_example_task_file_loads():
    """The bundled config/tasks.example.yaml loads on startup (SUBTASK 10.2)."""
    client = _client()
    body = client.get("/api/tasks").json()
    assert body["tasks"], "expected tasks from the bundled example"
    assert body["overall_progress"] == 0  # nothing run yet


def test_run_subtask_completes_with_status_and_output(tmp_path):
    """Running a subtask marks it done with output (SUBTASK 10.3)."""
    client = _client()
    client.post("/api/tasks/load", json={"content": EXAMPLE, "format": "yaml"})

    resp = client.post("/api/tasks/run", json={"task_id": "T1", "subtask_id": "T1.1"})
    assert resp.status_code == 200
    sub = resp.json()["subtask"]
    assert sub["status"] == "done"
    assert sub["output"]  # non-empty
    assert resp.json()["task"]["status"] == "in_progress"  # T1.2 still pending


def test_progress_updates_as_subtasks_complete(tmp_path):
    """Overall progress rises as subtasks complete (SUBTASK 10.4)."""
    client = _client()
    client.post("/api/tasks/load", json={"content": EXAMPLE, "format": "yaml"})
    assert client.get("/api/tasks").json()["overall_progress"] == 0

    # T1 is worth 40 across 2 subtasks -> completing one adds 20.
    p1 = client.post("/api/tasks/run", json={"task_id": "T1", "subtask_id": "T1.1"}).json()
    assert p1["overall_progress"] == 20.0

    # Completing T1.2 finishes T1 (task -> done), total 40.
    p2 = client.post("/api/tasks/run", json={"task_id": "T1", "subtask_id": "T1.2"}).json()
    assert p2["overall_progress"] == 40.0
    assert p2["task"]["status"] == "done"


def test_overall_progress_helper():
    tf = parse_task_file(EXAMPLE, "yaml")
    assert overall_progress(tf) == 0.0
    tf.tasks[1].subtasks[0].status = "done"  # T2's only subtask done -> 60
    assert overall_progress(tf) == 60.0


def test_run_missing_task_404():
    client = _client()
    resp = client.post("/api/tasks/run", json={"task_id": "NOPE", "subtask_id": "x"})
    assert resp.status_code == 404


def test_store_loads_from_yaml_path(tmp_path):
    path = tmp_path / "tasks.yaml"
    path.write_text(EXAMPLE)
    store = TaskStore(path)
    assert [t.id for t in store.task_file.tasks] == ["T1", "T2"]
