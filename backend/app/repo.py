"""Repository loader (TASK 4).

Loads a local repository: validates the path, scans its file tree while honoring
ignore rules (config ``ignore_paths`` + basic ``.gitignore`` patterns), detects
the project type, and persists lightweight session metadata so the last-loaded
repo survives an app reload.
"""

from __future__ import annotations

import fnmatch
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.config import REPO_ROOT, AppConfig

logger = logging.getLogger("hephaestus.repo")

router = APIRouter()

# Safety cap so a huge repo can't build an unbounded tree in one request.
_MAX_NODES = 5000

# Files whose presence at the repo root identifies a project type (SUBTASK 4.4).
_PROJECT_MARKERS: dict[str, tuple[str, ...]] = {
    "java": ("pom.xml", "build.gradle", "build.gradle.kts"),
    "node": ("package.json",),
    "python": ("pyproject.toml", "requirements.txt", "setup.py", "Pipfile"),
    "go": ("go.mod",),
    "rust": ("Cargo.toml",),
}


class RepoError(RuntimeError):
    """A user-safe repository error (``str(err)`` is safe to display)."""


class TreeNode(BaseModel):
    name: str
    path: str  # POSIX path relative to the repo root ("" for the root)
    type: str  # "dir" | "file"
    size: Optional[int] = None
    children: Optional[list["TreeNode"]] = None


class RepoMetadata(BaseModel):
    path: str
    name: str
    project_type: str
    file_count: int
    truncated: bool = False
    loaded_at: str


# --------------------------------------------------------------------------- #
# Ignore rules (SUBTASK 4.3)
# --------------------------------------------------------------------------- #
def _load_gitignore(root: Path) -> list[str]:
    """Parse simple ``.gitignore`` patterns (comments/blank lines skipped)."""
    gitignore = root / ".gitignore"
    if not gitignore.is_file():
        return []
    patterns: list[str] = []
    for line in gitignore.read_text(errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(line.rstrip("/"))
    return patterns


def _is_ignored(rel_posix: str, name: str, ignore_names: set[str], gitignore: list[str]) -> bool:
    if name in ignore_names:
        return True
    for pattern in gitignore:
        if fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(rel_posix, pattern):
            return True
    return False


# --------------------------------------------------------------------------- #
# Scanning (SUBTASK 4.2)
# --------------------------------------------------------------------------- #
def build_tree(root: Path, config: AppConfig) -> tuple[TreeNode, int, bool]:
    """Build a nested tree of the repo, returning (root_node, file_count, truncated)."""
    ignore_names = set(config.ignore_paths)
    gitignore = _load_gitignore(root)
    state = {"nodes": 0, "files": 0, "truncated": False}

    def walk(dir_path: Path, rel: str) -> list[TreeNode]:
        children: list[TreeNode] = []
        try:
            entries = sorted(
                os.scandir(dir_path),
                key=lambda e: (not e.is_dir(follow_symlinks=False), e.name.lower()),
            )
        except (PermissionError, FileNotFoundError):
            return children

        for entry in entries:
            child_rel = f"{rel}/{entry.name}" if rel else entry.name
            if _is_ignored(child_rel, entry.name, ignore_names, gitignore):
                continue
            if state["nodes"] >= _MAX_NODES:
                state["truncated"] = True
                break
            state["nodes"] += 1

            if entry.is_dir(follow_symlinks=False):
                children.append(
                    TreeNode(
                        name=entry.name,
                        path=child_rel,
                        type="dir",
                        children=walk(Path(entry.path), child_rel),
                    )
                )
            else:
                try:
                    size = entry.stat(follow_symlinks=False).st_size
                except OSError:
                    size = None
                state["files"] += 1
                children.append(TreeNode(name=entry.name, path=child_rel, type="file", size=size))
        return children

    root_children = walk(root, "")
    root_node = TreeNode(name=root.name, path="", type="dir", children=root_children)
    return root_node, state["files"], state["truncated"]


# --------------------------------------------------------------------------- #
# Project type (SUBTASK 4.4)
# --------------------------------------------------------------------------- #
def detect_project_type(root: Path) -> str:
    """Detect the project type from marker files at the root or one level deep.

    Scanning immediate subdirectories lets a monorepo (e.g. a Python backend
    beside a Node frontend) resolve to ``mixed``.
    """
    # Search the root and its direct subdirectories (skip hidden/common vendor dirs).
    search_dirs = [root]
    try:
        search_dirs += [
            entry
            for entry in root.iterdir()
            if entry.is_dir() and not entry.name.startswith(".") and entry.name != "node_modules"
        ]
    except OSError:
        pass

    found = {
        lang
        for base in search_dirs
        for lang, markers in _PROJECT_MARKERS.items()
        if any((base / marker).is_file() for marker in markers)
    }
    if not found:
        return "unknown"
    if len(found) == 1:
        return next(iter(found))
    return "mixed"


def load_repository(path: str, config: AppConfig) -> tuple[RepoMetadata, TreeNode]:
    """Validate and load a local repository (SUBTASK 4.1 / 4.2 / 4.4)."""
    candidate = Path(path).expanduser()
    if not candidate.exists():
        raise RepoError(f"Path does not exist: {path}")
    if not candidate.is_dir():
        raise RepoError(f"Not a directory: {path}")
    root = candidate.resolve()

    tree, file_count, truncated = build_tree(root, config)
    metadata = RepoMetadata(
        path=str(root),
        name=root.name,
        project_type=detect_project_type(root),
        file_count=file_count,
        truncated=truncated,
        loaded_at=datetime.now(timezone.utc).isoformat(),
    )
    logger.info("loaded repo %s (%s, %d files)", root, metadata.project_type, file_count)
    return metadata, tree


# --------------------------------------------------------------------------- #
# Session persistence (SUBTASK 4.5)
# --------------------------------------------------------------------------- #
class SessionStore:
    """Persists last-loaded repo metadata to a local JSON file."""

    def __init__(self, path: Path):
        self.path = path

    def save_repo(self, metadata: RepoMetadata) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"repo": metadata.model_dump()}, indent=2))

    def load_repo(self) -> Optional[RepoMetadata]:
        if not self.path.is_file():
            return None
        try:
            data = json.loads(self.path.read_text())
        except (json.JSONDecodeError, OSError):
            return None
        repo = data.get("repo")
        return RepoMetadata(**repo) if repo else None


def default_session_store() -> SessionStore:
    return SessionStore(REPO_ROOT / ".hephaestus" / "session.json")


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #
class LoadRepoRequest(BaseModel):
    path: str


@router.post("/api/repo/load")
def load_repo(request: LoadRepoRequest, http_request: Request) -> dict:
    """Load a local repository and persist its metadata for this session."""
    config: AppConfig = http_request.app.state.config
    try:
        metadata, tree = load_repository(request.path, config)
    except RepoError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    http_request.app.state.session_store.save_repo(metadata)
    return {"metadata": metadata, "tree": tree}


@router.get("/api/repo")
def get_repo(http_request: Request) -> dict:
    """Return the last-loaded repo metadata (SUBTASK 4.5), or null."""
    metadata = http_request.app.state.session_store.load_repo()
    return {"metadata": metadata}
