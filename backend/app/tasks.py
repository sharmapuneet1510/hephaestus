"""Agent task execution (TASK 10).

Defines a JSON/YAML task schema (10.1), loads and serves task files (10.2),
executes one subtask at a time (10.3 — mark in_progress → optional test run →
done/failed), and reports overall MVP progress (10.4).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import yaml
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.config import REPO_ROOT, AppConfig
from app.testrunner import run_command

router = APIRouter()

_STATUSES = ("pending", "in_progress", "done", "failed")


class Subtask(BaseModel):
    id: str
    title: str
    output: Optional[str] = None
    test: Optional[str] = None  # optional test command to run on execution
    status: str = "pending"


class Task(BaseModel):
    id: str
    title: str
    progress: float = 0  # this task's contribution to overall MVP progress
    status: str = "pending"
    subtasks: list[Subtask] = []


class TaskFile(BaseModel):
    tasks: list[Task] = []


def parse_task_file(text: str, fmt: str = "yaml") -> TaskFile:
    """Parse a JSON/YAML task file into a validated TaskFile (SUBTASK 10.1)."""
    try:
        data = json.loads(text) if fmt == "json" else yaml.safe_load(text)
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid task file: {exc}")
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Task file root must be a mapping")
    try:
        return TaskFile(**data)
    except Exception as exc:  # pydantic ValidationError -> clear message
        raise HTTPException(status_code=400, detail=f"Task file does not match schema: {exc}")


def overall_progress(task_file: TaskFile) -> float:
    """Overall MVP progress from completed subtasks, weighted by task progress."""
    total = 0.0
    for task in task_file.tasks:
        if not task.subtasks:
            total += task.progress if task.status == "done" else 0.0
            continue
        done = sum(1 for s in task.subtasks if s.status == "done")
        total += task.progress * done / len(task.subtasks)
    return round(total, 1)


def _refresh_task_status(task: Task) -> None:
    if not task.subtasks:
        return
    if all(s.status == "done" for s in task.subtasks):
        task.status = "done"
    elif any(s.status in ("in_progress", "done", "failed") for s in task.subtasks):
        task.status = "in_progress"


class TaskStore:
    def __init__(self, path: Optional[Path] = None):
        self.task_file = TaskFile()
        if path and path.is_file():
            try:
                fmt = "json" if path.suffix == ".json" else "yaml"
                self.task_file = parse_task_file(path.read_text(), fmt)
            except HTTPException:
                pass

    def set(self, task_file: TaskFile) -> None:
        self.task_file = task_file

    def run_subtask(
        self, task_id: str, subtask_id: str, config: AppConfig, repo_root: Optional[Path]
    ):
        task = next((t for t in self.task_file.tasks if t.id == task_id), None)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
        sub = next((s for s in task.subtasks if s.id == subtask_id), None)
        if not sub:
            raise HTTPException(status_code=404, detail=f"Subtask not found: {subtask_id}")

        sub.status = "in_progress"
        # Execute: run the subtask's test if it's an allowlisted command; else complete.
        if sub.test and repo_root and sub.test in set(config.test_commands.values()):
            result = run_command(sub.test, repo_root)
            sub.output = result.summary
            sub.status = "done" if result.passed else "failed"
        else:
            sub.output = sub.output or "Completed."
            sub.status = "done"

        _refresh_task_status(task)
        return task, sub


def default_task_store() -> TaskStore:
    return TaskStore(REPO_ROOT / "config" / "tasks.example.yaml")


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #
def _payload(store: TaskStore) -> dict:
    return {
        "tasks": store.task_file.tasks,
        "overall_progress": overall_progress(store.task_file),
    }


class LoadTasksRequest(BaseModel):
    content: str
    format: str = "yaml"


class RunSubtaskRequest(BaseModel):
    task_id: str
    subtask_id: str


@router.get("/api/tasks")
def get_tasks(http_request: Request) -> dict:
    return _payload(http_request.app.state.task_store)


@router.post("/api/tasks/load")
def load_tasks(request: LoadTasksRequest, http_request: Request) -> dict:
    store: TaskStore = http_request.app.state.task_store
    store.set(parse_task_file(request.content, request.format))
    return _payload(store)


@router.post("/api/tasks/run")
def run_subtask(request: RunSubtaskRequest, http_request: Request) -> dict:
    store: TaskStore = http_request.app.state.task_store
    config: AppConfig = http_request.app.state.config
    repo = http_request.app.state.session_store.load_repo()
    task, sub = store.run_subtask(
        request.task_id, request.subtask_id, config, Path(repo.path) if repo else None
    )
    return {
        "task": task,
        "subtask": sub,
        "overall_progress": overall_progress(store.task_file),
    }
