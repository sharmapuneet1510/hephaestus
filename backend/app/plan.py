"""Plan-first workflow (TASK 7).

Before any code change, Hephaestus produces a structured plan (goal, files,
steps, risks, tests, expected output — 7.1). A plan is held server-side as the
current pending plan; regenerating replaces it (7.3). Edits are guarded: an edit
attempt without an approved plan returns a safe error (7.4). Actual file editing
lands in TASK 8 — here the edit endpoint only enforces the plan-first gate.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.config import AppConfig
from app.context import ContextEngine

router = APIRouter()


class Plan(BaseModel):
    goal: str
    files_to_change: list[str] = []
    steps: list[str] = []
    risks: list[str] = []
    tests: list[str] = []
    expected_output: str
    failing_tests: Optional[str] = None  # failure context fed from TASK 9 (9.4)


class PlanState:
    """Holds the current pending plan and whether it has been approved."""

    def __init__(self) -> None:
        self.plan: Optional[Plan] = None
        self.approved: bool = False

    def set(self, plan: Plan) -> None:
        # Regenerating replaces the pending plan and resets approval (SUBTASK 7.3).
        self.plan = plan
        self.approved = False

    def approve(self) -> None:
        self.approved = True

    def clear(self) -> None:
        self.plan = None
        self.approved = False


def default_plan_state() -> PlanState:
    return PlanState()


def require_approved_plan(state: "PlanState") -> None:
    """Guard used by editing endpoints — enforce plan-first (SUBTASK 7.4)."""
    if not (state.plan and state.approved):
        raise HTTPException(
            status_code=400,
            detail="No approved plan. Create a plan and approve it before editing.",
        )


def build_plan(
    message: str,
    module: Optional[str],
    config: AppConfig,
    repo_path: Optional[str],
    engine: ContextEngine,
    failing_tests: Optional[str] = None,
) -> Plan:
    """Build a structured plan from a change request (SUBTASK 7.1).

    If ``failing_tests`` is provided (from the last test run — 9.4), it is folded
    into the plan so the fix targets the failure.
    """
    goal = message.strip() or "the requested change"

    files: list[str] = []
    if repo_path and module:
        try:
            ctx = engine.build(Path(repo_path), config, module=module)
            files = [m.path for m in ctx.files[:6]]
        except OSError:
            files = []

    focus_note = f" within `{module}`" if module else ""
    tests = sorted(set(config.test_commands.values())) or ["run the project's tests"]

    steps = [
        f"Inspect the relevant files{focus_note} and summarize current behavior.",
        "Draft the change and show a diff for review.",
        "Apply the change once approved.",
        "Run the affected tests and report results.",
    ]
    if failing_tests:
        steps.insert(0, f"Address the failing tests: {failing_tests}")

    return Plan(
        goal=goal,
        files_to_change=files,
        steps=steps,
        risks=[
            "The change may affect callers of any modified symbols.",
            "Existing tests may not cover the touched area.",
        ],
        tests=tests,
        expected_output=f"A minimal, reviewed change addressing: {goal}",
        failing_tests=failing_tests,
    )


class PlanRequest(BaseModel):
    message: str
    module: Optional[str] = None


@router.post("/api/plan")
def create_plan(request: PlanRequest, http_request: Request) -> dict:
    """Generate a plan and store it as the pending plan (SUBTASK 7.1 / 7.3)."""
    config: AppConfig = http_request.app.state.config
    repo = http_request.app.state.session_store.load_repo()
    engine: ContextEngine = http_request.app.state.context_engine

    # Fold the last failing test run into the plan (SUBTASK 9.4).
    last_test = http_request.app.state.test_state.last
    failing = last_test.summary if last_test and not last_test.passed else None

    plan = build_plan(
        request.message,
        request.module,
        config,
        repo.path if repo else None,
        engine,
        failing_tests=failing,
    )
    http_request.app.state.plan_state.set(plan)
    return {"plan": plan}


@router.get("/api/plan")
def get_plan(http_request: Request) -> dict:
    state: PlanState = http_request.app.state.plan_state
    return {"plan": state.plan, "approved": state.approved}


@router.post("/api/plan/approve")
def approve_plan(http_request: Request) -> dict:
    state: PlanState = http_request.app.state.plan_state
    if not state.plan:
        raise HTTPException(status_code=400, detail="No plan to approve — create a plan first.")
    state.approve()
    return {"approved": True}


@router.post("/api/edit")
def edit(http_request: Request) -> dict:
    """Plan-first gate probe (SUBTASK 7.4). Real editing is in app/edit.py (TASK 8)."""
    require_approved_plan(http_request.app.state.plan_state)
    return {"ok": True, "message": "Plan approved — ready to apply edits."}
