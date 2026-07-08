"""Final documentation generator (TASK 14).

Generates project documentation on demand — setup (14.1), usage (14.2), an
architecture summary reflecting the actually-mounted routes (14.3), and the agent
workflow guide with a sample task lifecycle (14.4).
"""

from __future__ import annotations

from fastapi import APIRouter, FastAPI, HTTPException, Request

router = APIRouter()

# One-line descriptions of the backend modules (reflected in the architecture doc).
_MODULES = {
    "config": "Typed configuration loader (config/default.yaml + ${ENV}).",
    "chat": "SSE streaming chat endpoint (real AI when configured, else mock).",
    "ai_client": "Anthropic-SDK client for the internal AI API.",
    "routing": "Request classifier + config-driven model tier selection.",
    "repo": "Repository loader: scan, ignore rules, project type, session store.",
    "context": "Context engine: chunking, markdown/JSON/TOON/graph, refresh.",
    "plan": "Plan-first workflow: structured plan, approval, edit guard.",
    "edit": "Workspace-safe file editing with unified diffs and revert.",
    "testrunner": "Detect + run test commands, summarize pass/fail.",
    "tasks": "Agent task execution: JSON/YAML tasks, run subtasks, progress.",
    "knowledge": "CLAUDE.md maintenance for the loaded repo.",
    "safety": "Workspace guard, command allow/block/confirm, secret redaction.",
}


def setup_guide() -> str:
    """Install, configure, and run steps (SUBTASK 14.1)."""
    return """\
# Setup Guide

## Prerequisites
- Python 3.11+, Node 20+ (uv recommended for the backend).

## Install
Backend:
```bash
cd backend
uv venv --python 3.11 .venv
uv pip install -e ".[dev]" --python .venv
```
Frontend:
```bash
cd frontend
npm install
```

## Configure
- Edit `config/default.yaml` (AI endpoint, model routing, ignore paths, test
  commands, safety rules).
- Set env vars (see `backend/.env.example`): `HEPHAESTUS_AI_ENDPOINT` and
  `HEPHAESTUS_AI_API_KEY` to enable real AI (the app runs without them using a mock).

## Run
- Single-origin (recommended): `npm run build` then `uvicorn app.main:app` and open
  the backend URL — it serves the built SPA and the API together.
- Dev: `uvicorn app.main:app --reload` (backend) + `npm run dev` (frontend, proxies /api).
"""


def usage_guide() -> str:
    """How to use the app (SUBTASK 14.2)."""
    return """\
# Usage Guide

1. **Load a repository** — paste a local path and click *Load*; the file tree and
   project type appear.
2. **Chat** — ask questions or request changes; responses stream in.
3. **Module focus** — click a folder's focus button or type `focus on <module>`;
   clear it with the chip's × or `clear focus`.
4. **Plan** — click *Plan* to get a structured plan (goal, files, steps, risks,
   tests, expected output).
5. **Apply** — enabled once a plan exists; approves the plan and applies edits
   (with a diff and revert).
6. **Test** — click *Test* to run the detected test command; pass/fail is shown.
7. **Save Context** — builds AI-friendly context (markdown/JSON/TOON/graph).
8. **Tasks** — run agent subtasks and track overall progress.
"""


def architecture_summary(app: FastAPI) -> str:
    """Architecture doc reflecting the mounted modules and routes (SUBTASK 14.3)."""
    lines = ["# Architecture Summary", "", "## Modules"]
    for name, desc in _MODULES.items():
        lines.append(f"- `app/{name}.py` — {desc}")

    lines += ["", "## API Endpoints"]
    seen: set[tuple[str, str]] = set()

    def walk(routes) -> None:
        for route in routes:
            # Included routers are nested; reach their routes via .routes or
            # ._IncludedRouter.original_router.routes depending on the version.
            original = getattr(route, "original_router", None)
            nested = getattr(route, "routes", None) or getattr(original, "routes", None)
            if nested:
                walk(nested)
            path = getattr(route, "path", "")
            methods = getattr(route, "methods", None)
            if not methods or not path.startswith("/api/"):
                continue
            for method in methods:
                if method in ("GET", "POST", "DELETE", "PATCH"):
                    seen.add((method, path))

    walk(app.routes)
    for method, path in sorted(seen, key=lambda x: (x[1], x[0])):
        lines.append(f"- `{method} {path}`")

    lines += [
        "",
        "## Stack",
        "- Backend: Python/FastAPI (app factory in `app/main.py`).",
        "- Frontend: React + TypeScript + Vite + Monaco (the 'Forge' UI).",
        "- The backend serves the built SPA single-origin in production.",
    ]
    return "\n".join(lines) + "\n"


def agent_workflow_guide() -> str:
    """Agent/task workflow with a sample lifecycle (SUBTASK 14.4)."""
    return """\
# Agent Workflow Guide

## Task files
Tasks are defined in a JSON/YAML file (see `config/tasks.example.yaml`) as tasks →
subtasks, each with a status and an optional test command.

## Executing a subtask
Running a subtask flows through: **plan → apply → test → update knowledge**.
- The subtask is marked `in_progress`, its allowlisted test (if any) runs, and it
  becomes `done` or `failed` with output.
- Overall MVP progress updates from completed subtasks.

## CLAUDE.md updates
After meaningful work (e.g. Apply), a concise, de-duplicated note is recorded to
the loaded repo's `CLAUDE.md`, and that knowledge is folded into future prompts.

## Test flow
The detected test command (npm test / mvn test / gradle test / pytest) runs via a
controlled executor; failures feed into the next plan.

## Sample lifecycle
1. Load a repo and set module focus.
2. Ask for a change; click *Plan* to get a structured plan.
3. Click *Apply* (plan-first guard enforced) to apply edits; review the diff.
4. Click *Test*; if it fails, the failure is added to the next plan.
5. The completed work is recorded to `CLAUDE.md`; task progress advances.
"""


_GENERATORS = {
    "setup": setup_guide,
    "usage": usage_guide,
    "agent": agent_workflow_guide,
}


@router.get("/api/docs")
def generate_docs(http_request: Request, kind: str = "all") -> dict:
    """Generate documentation on demand (SUBTASK 14.1–14.4)."""
    if kind == "architecture":
        return {"kind": kind, "content": architecture_summary(http_request.app)}
    if kind in _GENERATORS:
        return {"kind": kind, "content": _GENERATORS[kind]()}
    if kind == "all":
        parts = [
            setup_guide(),
            usage_guide(),
            architecture_summary(http_request.app),
            agent_workflow_guide(),
        ]
        return {"kind": "all", "content": "\n\n---\n\n".join(parts)}
    raise HTTPException(status_code=400, detail=f"Unknown docs kind: {kind}")
