"""File editing and diff review (TASK 8).

Reads and edits files strictly inside the loaded repository (workspace-only —
8.1), applies controlled edits behind the plan-first guard (8.2), returns unified
diffs (8.3), supports revert from in-memory backups (8.4), and tracks touched
files (8.5).
"""

from __future__ import annotations

import difflib
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.plan import PlanState, require_approved_plan
from app.safety import resolve_in_workspace

router = APIRouter()


class EditSession:
    """Tracks original file contents so edits can be reverted (8.4 / 8.5)."""

    def __init__(self) -> None:
        # rel_path -> original content, or None when the file was newly created.
        self.backups: dict[str, Optional[str]] = {}

    def record(self, rel_path: str, original: Optional[str]) -> None:
        self.backups.setdefault(rel_path, original)

    def touched(self) -> list[str]:
        return sorted(self.backups.keys())

    def clear(self) -> None:
        self.backups.clear()


def default_edit_session() -> EditSession:
    return EditSession()


def _repo_root(http_request: Request) -> Path:
    repo = http_request.app.state.session_store.load_repo()
    if not repo:
        raise HTTPException(status_code=400, detail="No repository loaded")
    return Path(repo.path)


def unified_diff(old: str, new: str, rel_path: str) -> str:
    return "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{rel_path}",
            tofile=f"b/{rel_path}",
        )
    )


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #
class EditRequest(BaseModel):
    path: str
    new_content: str


@router.get("/api/file")
def read_file(path: str, http_request: Request) -> dict:
    """Read a file inside the loaded repo (SUBTASK 8.1 — workspace-only)."""
    root = _repo_root(http_request)
    target = resolve_in_workspace(root, path)
    if not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return {"path": path, "content": target.read_text(errors="ignore")}


@router.post("/api/edit/preview")
def preview_edit(request: EditRequest, http_request: Request) -> dict:
    """Return the diff for a proposed edit without applying it (SUBTASK 8.3)."""
    root = _repo_root(http_request)
    target = resolve_in_workspace(root, request.path)
    old = target.read_text(errors="ignore") if target.is_file() else ""
    return {"path": request.path, "diff": unified_diff(old, request.new_content, request.path)}


@router.post("/api/edit/apply")
def apply_edit(request: EditRequest, http_request: Request) -> dict:
    """Apply an edit to one file (SUBTASK 8.2) behind the plan-first guard (7.4)."""
    require_approved_plan(http_request.app.state.plan_state)
    root = _repo_root(http_request)
    target = resolve_in_workspace(root, request.path)

    created = not target.is_file()
    old = "" if created else target.read_text(errors="ignore")

    session: EditSession = http_request.app.state.edit_session
    session.record(request.path, None if created else old)

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(request.new_content)

    return {
        "path": request.path,
        "created": created,
        "diff": unified_diff(old, request.new_content, request.path),
        "touched": session.touched(),
    }


@router.post("/api/edit/revert")
def revert_edits(http_request: Request) -> dict:
    """Restore all edited files to their original content (SUBTASK 8.4)."""
    root = _repo_root(http_request)
    session: EditSession = http_request.app.state.edit_session
    reverted: list[str] = []
    for rel_path, original in session.backups.items():
        target = resolve_in_workspace(root, rel_path)
        if original is None:
            target.unlink(missing_ok=True)  # was newly created — remove it
        else:
            target.write_text(original)
        reverted.append(rel_path)
    session.clear()
    return {"reverted": sorted(reverted)}


@router.get("/api/edit/status")
def edit_status(http_request: Request) -> dict:
    """List files touched in this session (SUBTASK 8.5)."""
    session: EditSession = http_request.app.state.edit_session
    return {"files": session.touched()}
