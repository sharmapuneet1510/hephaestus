"""Test runner (TASK 9).

Detects the project's test command (9.1), runs it through a controlled executor
capturing output/exit/duration (9.2), summarizes pass/fail with failed files and
an error snippet (9.3), and stores the last result so failures can be fed into
the next plan (9.4 — see app/plan.py).
"""

from __future__ import annotations

import re
import shlex
import subprocess
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.config import AppConfig

router = APIRouter()

_OUTPUT_LIMIT = 6000  # keep the tail of long output


class TestResult(BaseModel):
    __test__ = False  # not a pytest test class
    command: str
    exit_code: int
    passed: bool
    duration_ms: int
    summary: str
    output: str
    failed_files: list[str] = []


class TestState:
    """Holds the most recent test result (fed into the next plan — 9.4)."""

    __test__ = False  # not a pytest test class

    def __init__(self) -> None:
        self.last: Optional[TestResult] = None


def default_test_state() -> TestState:
    return TestState()


# --------------------------------------------------------------------------- #
# 9.1 — Detection
# --------------------------------------------------------------------------- #
def _search_dirs(root: Path) -> list[Path]:
    dirs = [root]
    try:
        dirs += [
            e
            for e in root.iterdir()
            if e.is_dir() and not e.name.startswith(".") and e.name != "node_modules"
        ]
    except OSError:
        pass
    return dirs


def detect_test_command(root: Path, config: AppConfig) -> Optional[str]:
    """Detect the test command from marker files at the root or one level deep."""
    tc = config.test_commands
    checks: list[tuple[str, tuple[str, ...]]] = [
        ("java_maven", ("pom.xml",)),
        ("java_gradle", ("build.gradle", "build.gradle.kts")),
        ("node", ("package.json",)),
        ("python", ("pyproject.toml", "setup.py", "requirements.txt", "pytest.ini", "tox.ini")),
    ]
    dirs = _search_dirs(root)
    for key, markers in checks:
        if key not in tc:
            continue
        for base in dirs:
            if any((base / marker).is_file() for marker in markers):
                return tc[key]
    # Fall back to python if a tests/ directory exists.
    if "python" in tc and any((d / "tests").is_dir() for d in dirs):
        return tc["python"]
    return None


# --------------------------------------------------------------------------- #
# 9.2 / 9.3 — Execution + summary
# --------------------------------------------------------------------------- #
_FAILED_FILE_PATTERNS = [
    re.compile(r"FAILED\s+(\S+?)::"),  # pytest
    re.compile(r"^(?:FAIL|ERROR)\s+(\S+)", re.MULTILINE),  # generic
]
# Capture the whole line that carries a pass/fail count (e.g. "1 failed, 2 passed").
_SUMMARY_PATTERN = re.compile(r"^(.*\b\d+\s+(?:passed|failed|errors?|skipped)\b.*)$", re.MULTILINE)


def _extract_failed_files(output: str) -> list[str]:
    found: list[str] = []
    for pattern in _FAILED_FILE_PATTERNS:
        for match in pattern.findall(output):
            if match not in found:
                found.append(match)
    return found


def _summarize(output: str, passed: bool, exit_code: int) -> str:
    matches = _SUMMARY_PATTERN.findall(output)
    if matches:
        return matches[-1].strip()
    tail = [ln for ln in output.strip().splitlines() if ln.strip()]
    if tail:
        return tail[-1].strip()
    return "Tests passed" if passed else f"Tests failed (exit {exit_code})"


def run_command(command: str, cwd: Path, timeout: int = 120) -> TestResult:
    """Run a test command in ``cwd`` and capture the result (9.2 / 9.3)."""
    args = shlex.split(command)
    start = time.monotonic()
    try:
        proc = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, timeout=timeout)
        output = (proc.stdout or "") + (proc.stderr or "")
        exit_code = proc.returncode
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + (exc.stderr or "") + f"\n(timed out after {timeout}s)"
        exit_code = 124
    except FileNotFoundError:
        duration_ms = int((time.monotonic() - start) * 1000)
        return TestResult(
            command=command,
            exit_code=127,
            passed=False,
            duration_ms=duration_ms,
            summary=f"Command not found: {args[0] if args else command}",
            output="",
            failed_files=[],
        )

    duration_ms = int((time.monotonic() - start) * 1000)
    passed = exit_code == 0
    return TestResult(
        command=command,
        exit_code=exit_code,
        passed=passed,
        duration_ms=duration_ms,
        summary=_summarize(output, passed, exit_code),
        output=output[-_OUTPUT_LIMIT:],
        failed_files=_extract_failed_files(output),
    )


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #
def _repo_root(http_request: Request) -> Path:
    repo = http_request.app.state.session_store.load_repo()
    if not repo:
        raise HTTPException(status_code=400, detail="No repository loaded")
    return Path(repo.path)


class TestRunRequest(BaseModel):
    __test__ = False  # not a pytest test class
    command: Optional[str] = None


@router.get("/api/test/detect")
def detect(http_request: Request) -> dict:
    root = _repo_root(http_request)
    config: AppConfig = http_request.app.state.config
    return {"command": detect_test_command(root, config)}


@router.post("/api/test")
def run_tests(request: TestRunRequest, http_request: Request) -> TestResult:
    """Run the detected (or an allowlisted) test command (SUBTASK 9.2 / 9.3)."""
    root = _repo_root(http_request)
    config: AppConfig = http_request.app.state.config

    detected = detect_test_command(root, config)
    command = request.command or detected
    if not command:
        raise HTTPException(status_code=400, detail="No test command detected for this repository.")

    # Only run detected/configured commands — no arbitrary shell (safety).
    allowed = set(config.test_commands.values())
    if command != detected and command not in allowed:
        raise HTTPException(
            status_code=400, detail="Command not allowed. Use a configured test command."
        )

    result = run_command(command, root, timeout=config.ai.timeout_seconds or 120)
    http_request.app.state.test_state.last = result
    return result
