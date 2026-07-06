"""Tests for the health endpoint (SUBTASK 1.4)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import load_config
from app.main import create_app


def _client(environ: dict) -> TestClient:
    config = load_config(environ=environ)
    return TestClient(create_app(config=config))


def test_health_ok_without_ai_configured():
    """Backend boots and reports healthy even with no AI key (SUBTASK 1.4)."""
    client = _client(environ={})
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "hephaestus-backend"
    assert body["ai_configured"] is False
    assert "config" in body


def test_health_reports_ai_configured_when_env_set():
    client = _client(
        environ={
            "HEPHAESTUS_AI_ENDPOINT": "https://ai.example.com/v1",
            "HEPHAESTUS_AI_API_KEY": "secret",
        }
    )
    body = client.get("/api/health").json()
    assert body["ai_configured"] is True


def test_health_does_not_leak_api_key():
    client = _client(
        environ={
            "HEPHAESTUS_AI_ENDPOINT": "https://ai.example.com/v1",
            "HEPHAESTUS_AI_API_KEY": "super-secret",
        }
    )
    assert "super-secret" not in client.get("/api/health").text
