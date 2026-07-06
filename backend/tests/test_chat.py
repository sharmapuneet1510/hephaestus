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
        parts.append(json.loads(data)["delta"])
    return "".join(parts)


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
