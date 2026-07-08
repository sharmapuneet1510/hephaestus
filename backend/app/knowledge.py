"""CLAUDE.md knowledge maintenance (TASK 11).

Maintains a ``CLAUDE.md`` at the **loaded repository's** root (distinct from this
project's own CLAUDE.md): creates it from a template if missing (11.1), appends
concise, de-duplicated notes after meaningful work (11.2 / 11.3), and exposes the
stored knowledge for inclusion in prompts (11.4 — see app/chat.py).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.config import AppConfig

router = APIRouter()

CLAUDE_MD_SECTIONS = [
    "Project Overview",
    "Architecture Notes",
    "Important Commands",
    "Test Commands",
    "Coding Conventions",
    "Config Conventions",
    "Current Constraints",
    "Completed Task Notes",
    "Known Issues",
]

_DEFAULT_SECTION = "Completed Task Notes"


def template(repo_name: str) -> str:
    """A CLAUDE.md scaffold with the required sections (SUBTASK 11.1)."""
    lines = [
        "# CLAUDE.md",
        "",
        f"Project knowledge for **{repo_name}**, maintained by Hephaestus for future AI sessions.",
        "",
    ]
    for section in CLAUDE_MD_SECTIONS:
        lines.append(f"## {section}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _claude_path(repo_root: Path, config: AppConfig) -> Path:
    return repo_root / config.claude_md.path


def ensure(repo_root: Path, config: AppConfig) -> tuple[bool, str]:
    """Create CLAUDE.md from the template if missing; return (created, content)."""
    path = _claude_path(repo_root, config)
    if path.is_file():
        return False, path.read_text(errors="ignore")
    content = template(repo_root.name)
    path.write_text(content)
    return True, content


def add_note(
    repo_root: Path, config: AppConfig, note: str, section: str = _DEFAULT_SECTION
) -> tuple[bool, str]:
    """Append a concise, de-duplicated bullet under a section (11.2 / 11.3)."""
    ensure(repo_root, config)
    path = _claude_path(repo_root, config)
    content = path.read_text(errors="ignore")

    bullet = f"- {note.strip()}"
    if bullet in content:
        return False, content  # already recorded — no noisy duplicate (SUBTASK 11.3)

    lines = content.splitlines()
    heading = f"## {section}"
    try:
        idx = next(i for i, ln in enumerate(lines) if ln.strip().lower() == heading.lower())
        lines.insert(idx + 1, bullet)
    except StopIteration:
        # Section missing — append it.
        lines += ["", heading, bullet]

    new_content = "\n".join(lines).rstrip() + "\n"
    path.write_text(new_content)
    return True, new_content


def build_prompt_preamble(repo_root: Path, config: AppConfig) -> str:
    """Return CLAUDE.md content for inclusion in prompts (SUBTASK 11.4)."""
    path = _claude_path(repo_root, config)
    if not path.is_file():
        return ""
    return (
        f"Project knowledge from the repository's CLAUDE.md:\n\n{path.read_text(errors='ignore')}\n"
    )


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #
def _repo_root(http_request: Request) -> Path:
    repo = http_request.app.state.session_store.load_repo()
    if not repo:
        raise HTTPException(status_code=400, detail="No repository loaded")
    return Path(repo.path)


class NoteRequest(BaseModel):
    note: str
    section: str = _DEFAULT_SECTION


@router.get("/api/knowledge")
def get_knowledge(http_request: Request) -> dict:
    root = _repo_root(http_request)
    config: AppConfig = http_request.app.state.config
    path = _claude_path(root, config)
    return {
        "exists": path.is_file(),
        "content": path.read_text(errors="ignore") if path.is_file() else "",
    }


@router.post("/api/knowledge/ensure")
def ensure_knowledge(http_request: Request) -> dict:
    root = _repo_root(http_request)
    created, content = ensure(root, http_request.app.state.config)
    return {"created": created, "content": content}


@router.post("/api/knowledge/note")
def add_knowledge_note(request: NoteRequest, http_request: Request) -> dict:
    root = _repo_root(http_request)
    added, content = add_note(root, http_request.app.state.config, request.note, request.section)
    return {"added": added, "content": content}
