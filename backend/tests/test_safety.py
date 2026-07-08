"""Tests for safety and permissions (TASK 12)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.ai_client import to_anthropic_messages
from app.chat import ChatMessage
from app.config import load_config
from app.main import create_app
from app.safety import (
    classify_command,
    is_within_workspace,
    redact_secrets,
    resolve_in_workspace,
)


def _config():
    return load_config(environ={})


# --------------------------------------------------------------------------- #
# 12.1 — Workspace boundary
# --------------------------------------------------------------------------- #
def test_workspace_boundary(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    assert is_within_workspace(root, "src/a.py") is True
    assert is_within_workspace(root, "../secret") is False
    assert resolve_in_workspace(root, "src/a.py") == (root / "src/a.py").resolve()
    with pytest.raises(HTTPException):
        resolve_in_workspace(root, "../../etc/passwd")


# --------------------------------------------------------------------------- #
# 12.2 / 12.3 — Command classification
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "command,expected",
    [
        ("rm -rf /", "blocked"),
        ("cat /etc/shadow", "blocked"),
        ("cat ~/.ssh/id_rsa", "blocked"),
        ("shutdown -h now", "blocked"),
        ("pip install requests", "confirm"),
        ("npm install", "confirm"),
        ("git push origin main", "confirm"),
        ("ls -la", "allow"),
        ("pytest", "allow"),
    ],
)
def test_classify_command(command, expected):
    decision, _ = classify_command(command, _config().safety)
    assert decision == expected


def test_command_check_endpoint():
    client = TestClient(create_app(config=_config()))
    assert (
        client.post("/api/command/check", json={"command": "rm -rf /"}).json()["decision"]
        == "blocked"
    )
    assert (
        client.post("/api/command/check", json={"command": "npm install"}).json()["decision"]
        == "confirm"
    )
    assert (
        client.post("/api/command/check", json={"command": "echo hi"}).json()["decision"] == "allow"
    )


# --------------------------------------------------------------------------- #
# 12.4 — Secret redaction
# --------------------------------------------------------------------------- #
def test_redact_tokens():
    text = "key sk-abcd1234efgh5678ijkl and aws AKIAIOSFODNN7EXAMPLE done"
    out = redact_secrets(text)
    assert "sk-abcd1234efgh5678ijkl" not in out
    assert "AKIAIOSFODNN7EXAMPLE" not in out
    assert out.count("[REDACTED]") == 2


def test_redact_key_value():
    out = redact_secrets("config: api_key = 'supersecretvalue12345'")
    assert "supersecretvalue12345" not in out
    assert "[REDACTED]" in out
    assert "api_key" in out  # the key name is preserved


def test_redact_bearer_and_github():
    out = redact_secrets(
        "Authorization: Bearer abcdef1234567890ABCDEF token ghp_abcdefghij1234567890XYZ"
    )
    assert "abcdef1234567890ABCDEF" not in out
    assert "ghp_abcdefghij1234567890XYZ" not in out


def test_ai_messages_are_redacted():
    """Outbound AI messages have secrets masked (SUBTASK 12.4)."""
    msgs = [ChatMessage(role="user", content="my token is sk-abcd1234efgh5678ijkl please use it")]
    out = to_anthropic_messages(msgs)
    assert "sk-abcd1234efgh5678ijkl" not in out[0]["content"]
    assert "[REDACTED]" in out[0]["content"]


def test_no_false_positive_on_plain_text():
    text = "This is a normal sentence about the login form."
    assert redact_secrets(text) == text
