"""Tests for the mock chat SSE endpoint (SUBTASK 2.2 / 2.3)."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.config import load_config
from app.main import create_app


def _client() -> TestClient:
    return TestClient(create_app(config=load_config(environ={})))


def _collect_deltas(sse_text: str) -> str:
    """Reassemble the streamed reply from raw SSE text."""
    parts: list[str] = []
    for line in sse_text.splitlines():
        if not line.startswith("data: "):
            continue
        data = line[len("data: ") :]
        if data == "[DONE]":
            continue
        payload = json.loads(data)
        if "delta" in payload:
            parts.append(payload["delta"])
    return "".join(parts)


def _ai_client(environ: dict) -> TestClient:
    return TestClient(create_app(config=load_config(environ=environ)))


_AI_ENV = {
    "HEPHAESTUS_AI_ENDPOINT": "https://ai.internal.test",
    "HEPHAESTUS_AI_API_KEY": "k",
}


class _FakeAIClient:
    """Stand-in for AIClient that streams two deltas (SUBTASK 3.2)."""

    def __init__(self, config, http_client=None):
        pass

    async def stream(self, messages, *, model, system=None, max_tokens=None):
        yield "Hello "
        yield "world"

    async def aclose(self):
        pass


class _FailingAIClient(_FakeAIClient):
    async def stream(self, messages, *, model, system=None, max_tokens=None):
        from app.ai_client import AIError

        raise AIError("simulated failure")
        yield  # pragma: no cover - unreachable


def test_chat_uses_real_ai_when_configured(monkeypatch):
    import app.ai_client as ai

    monkeypatch.setattr(ai, "AIClient", _FakeAIClient)
    resp = _ai_client(_AI_ENV).post(
        "/api/chat", json={"messages": [{"role": "user", "content": "refactor the module"}]}
    )
    assert resp.status_code == 200
    # SUBTASK 3.4: a routing meta event names the selected model + tier.
    assert '"model"' in resp.text and '"tier": "strong"' in resp.text
    # SUBTASK 3.2: the real reply streams through.
    assert _collect_deltas(resp.text) == "Hello world"
    assert resp.text.strip().endswith("data: [DONE]")


def test_chat_reports_ai_error_as_safe_delta(monkeypatch):
    import app.ai_client as ai

    monkeypatch.setattr(ai, "AIClient", _FailingAIClient)
    resp = _ai_client(_AI_ENV).post(
        "/api/chat", json={"messages": [{"role": "user", "content": "hi"}]}
    )
    # SUBTASK 3.3: the failure surfaces as a user-safe message, not a crash.
    assert resp.status_code == 200
    assert "simulated failure" in _collect_deltas(resp.text)
    assert resp.text.strip().endswith("data: [DONE]")


def test_chat_streams_event_stream_content_type():
    client = _client()
    resp = client.post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")


def test_chat_stream_terminates_with_done():
    client = _client()
    resp = client.post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert resp.text.strip().endswith("data: [DONE]")


def test_chat_reply_is_plan_first_and_echoes_prompt():
    client = _client()
    resp = client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "add a login form"}]},
    )
    reply = _collect_deltas(resp.text)
    assert "plan" in reply.lower()
    assert "add a login form" in reply
    # SUBTASK 2.4: reply carries a fenced code block for the UI to render.
    assert "```python" in reply


def test_chat_includes_module_focus_when_provided():
    client = _client()
    resp = client.post(
        "/api/chat",
        json={
            "messages": [{"role": "user", "content": "refactor"}],
            "module": "checkout",
        },
    )
    reply = _collect_deltas(resp.text)
    assert "checkout" in reply


def test_chat_reassembled_stream_matches_build_mock_reply():
    """Chunking is lossless: streamed deltas reassemble to the exact reply."""
    from app.chat import ChatRequest, build_mock_reply

    req = ChatRequest(messages=[{"role": "user", "content": "hello forge"}])
    expected = build_mock_reply(req)

    client = _client()
    resp = client.post("/api/chat", json=req.model_dump())
    assert _collect_deltas(resp.text) == expected
