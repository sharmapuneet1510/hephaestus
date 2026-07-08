"""Safety and permissions (TASK 12).

Centralizes the guards that protect the user's machine: a workspace boundary for
file access (12.1), an allow/block/confirm classifier for shell commands
(12.2 / 12.3), and secret redaction for anything sent to the AI or logs (12.4).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from app.config import AppConfig, SafetyConfig

router = APIRouter()


# --------------------------------------------------------------------------- #
# 12.1 — Workspace boundary
# --------------------------------------------------------------------------- #
def is_within_workspace(root: Path, rel_path: str) -> bool:
    root_res = root.resolve()
    candidate = (root_res / rel_path).resolve()
    return candidate == root_res or str(candidate).startswith(f"{root_res}{os.sep}")


def resolve_in_workspace(root: Path, rel_path: str) -> Path:
    """Resolve ``rel_path`` under ``root``, rejecting anything outside it."""
    if not is_within_workspace(root, rel_path):
        raise HTTPException(status_code=400, detail="Path is outside the workspace.")
    return (root.resolve() / rel_path).resolve()


# --------------------------------------------------------------------------- #
# 12.2 / 12.3 — Command classification
# --------------------------------------------------------------------------- #
Decision = str  # "allow" | "confirm" | "blocked"


def classify_command(command: str, safety: SafetyConfig) -> tuple[Decision, str]:
    """Classify a shell command as allow / confirm / blocked (12.2 / 12.3)."""
    lowered = command.lower()
    for pattern in safety.blocked_command_patterns:
        if pattern.lower() in lowered:
            return "blocked", f"Blocked: matches destructive pattern '{pattern}'."
    for pattern in safety.confirm_command_patterns:
        if pattern.lower() in lowered:
            return "confirm", f"Requires confirmation: matches '{pattern}'."
    return "allow", "Command is allowed."


# --------------------------------------------------------------------------- #
# 12.4 — Secret redaction
# --------------------------------------------------------------------------- #
_REDACTED = "[REDACTED]"

# Whole-match token patterns (replaced entirely).
_TOKEN_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9\-]{12,}"),  # Anthropic
    re.compile(r"sk-[A-Za-z0-9]{16,}"),  # OpenAI-style
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),  # GitHub PAT
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS access key id
    re.compile(r"AIza[0-9A-Za-z\-_]{20,}"),  # Google API key
    re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}"),  # Slack
    re.compile(r"(?i)bearer\s+[A-Za-z0-9\-_.=]{16,}"),  # Bearer tokens
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),  # private key blocks
]

# key = value assignments (only the value is masked).
_KV_PATTERN = re.compile(
    r"(?i)\b(api[_-]?key|secret|token|password|passwd|access[_-]?key)\b(\s*[:=]\s*)"
    r"['\"]?([A-Za-z0-9\-_./+]{8,})['\"]?"
)


def redact_secrets(text: str) -> str:
    """Mask API keys / tokens / secrets before sending to AI or logs (12.4)."""
    if not text:
        return text
    redacted = _KV_PATTERN.sub(lambda m: f"{m.group(1)}{m.group(2)}{_REDACTED}", text)
    for pattern in _TOKEN_PATTERNS:
        redacted = pattern.sub(_REDACTED, redacted)
    return redacted


# --------------------------------------------------------------------------- #
# Endpoint
# --------------------------------------------------------------------------- #
from pydantic import BaseModel  # noqa: E402  (kept near use)


class CommandCheckRequest(BaseModel):
    command: str


@router.post("/api/command/check")
def check_command(request: CommandCheckRequest, http_request: Request) -> dict:
    """Return the safety decision for a command (UI can gate on it)."""
    config: AppConfig = http_request.app.state.config
    decision, reason = classify_command(request.command, config.safety)
    return {"decision": decision, "reason": reason}
