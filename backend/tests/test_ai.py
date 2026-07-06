"""Tests for the AI client (SUBTASK 3.1 / 3.2 / 3.3).

Uses an injected ``httpx.MockTransport`` so the Anthropic SDK's real request/
response mapping is exercised without a live API.
"""

from __future__ import annotations

import httpx
import pytest

from app.ai_client import AIClient, AIError, to_anthropic_messages
from app.chat import ChatMessage
from app.config import load_config

# A minimal but valid Anthropic Messages streaming (SSE) response.
_SSE_OK = (
    "event: message_start\n"
    'data: {"type":"message_start","message":{"id":"msg_1","type":"message",'
    '"role":"assistant","model":"claude-opus-4-8","content":[],"stop_reason":null,'
    '"stop_sequence":null,"usage":{"input_tokens":5,"output_tokens":0}}}\n\n'
    "event: content_block_start\n"
    'data: {"type":"content_block_start","index":0,'
    '"content_block":{"type":"text","text":""}}\n\n'
    "event: content_block_delta\n"
    'data: {"type":"content_block_delta","index":0,'
    '"delta":{"type":"text_delta","text":"Here is "}}\n\n'
    "event: content_block_delta\n"
    'data: {"type":"content_block_delta","index":0,'
    '"delta":{"type":"text_delta","text":"the plan."}}\n\n'
    "event: content_block_stop\n"
    'data: {"type":"content_block_stop","index":0}\n\n'
    "event: message_delta\n"
    'data: {"type":"message_delta","delta":{"stop_reason":"end_turn",'
    '"stop_sequence":null},"usage":{"output_tokens":4}}\n\n'
    "event: message_stop\n"
    'data: {"type":"message_stop"}\n\n'
)


def _config():
    return load_config(
        environ={
            "HEPHAESTUS_AI_ENDPOINT": "https://ai.internal.test",
            "HEPHAESTUS_AI_API_KEY": "test-key",
        }
    )


def _client(handler) -> AIClient:
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport, base_url="https://ai.internal.test")
    return AIClient(_config(), http_client=http_client)


async def _collect(client: AIClient) -> str:
    parts = []
    async for text in client.stream(
        [{"role": "user", "content": "add a login form"}], model="claude-opus-4-8"
    ):
        parts.append(text)
    return "".join(parts)


def test_to_anthropic_messages_coerces_roles():
    msgs = [
        ChatMessage(role="user", content="hi"),
        ChatMessage(role="assistant", content="hello"),
        ChatMessage(role="tool", content="x"),  # coerced to user
    ]
    out = to_anthropic_messages(msgs)
    assert out[0] == {"role": "user", "content": "hi"}
    assert out[1] == {"role": "assistant", "content": "hello"}
    assert out[2]["role"] == "user"


async def test_stream_maps_sse_to_text_deltas():
    """A valid streaming response is reassembled to the model's text (3.1/3.2)."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/messages"
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=_SSE_OK)

    client = _client(handler)
    try:
        assert await _collect(client) == "Here is the plan."
    finally:
        await client.aclose()


async def test_auth_error_maps_to_user_safe_message():
    """A 401 becomes a clear, non-leaky AIError (3.3)."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={"type": "error", "error": {"type": "authentication_error", "message": "bad key"}},
        )

    client = _client(handler)
    try:
        with pytest.raises(AIError) as exc:
            await _collect(client)
        assert exc.value.status == 401
        assert "authentication failed" in str(exc.value).lower()
    finally:
        await client.aclose()


async def test_server_error_maps_to_retry_message():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            500,
            json={"type": "error", "error": {"type": "api_error", "message": "boom"}},
        )

    client = _client(handler)
    try:
        with pytest.raises(AIError) as exc:
            await _collect(client)
        assert exc.value.status == 500
        assert "server error" in str(exc.value).lower()
    finally:
        await client.aclose()


async def test_timeout_maps_to_timeout_message():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    client = _client(handler)
    try:
        with pytest.raises(AIError) as exc:
            await _collect(client)
        assert "timed out" in str(exc.value).lower()
    finally:
        await client.aclose()
