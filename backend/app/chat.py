"""Chat endpoint (TASK 2 / TASK 3).

Streams an assistant reply over Server-Sent Events. When AI is configured
(TASK 3), the request is routed to a model and streamed from the internal AI API
via ``app.ai_client``; otherwise it falls back to a deterministic, plan-first
**mock** reply (TASK 2) so the UI can be built and tested without AI.

Wire protocol (SSE): each event is ``data: {"delta": "..."}`` (plus an initial
``data: {"model": ..., "tier": ...}`` routing meta event on the real path) and
the stream terminates with ``data: [DONE]``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

router = APIRouter()
logger = logging.getLogger("hephaestus.chat")

# Per-token delay for the streaming effect. Tests set this to 0 for speed.
_STREAM_DELAY_S = float(os.environ.get("HEPHAESTUS_STREAM_DELAY_S", "0.02"))

# Splits text into whitespace-preserving tokens so the reassembled stream is
# byte-identical to the source (code fences survive intact).
_TOKENIZER = re.compile(r"\S+\s*|\s+")


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(default_factory=list)
    module: str | None = None


def build_mock_reply(request: ChatRequest) -> str:
    """Deterministic, plan-first mock reply referencing the user's input."""
    last_user = next(
        (m.content for m in reversed(request.messages) if m.role == "user"),
        "",
    )
    focus = f" (module focus: **{request.module}**)" if request.module else ""
    prompt = last_user.strip() or "your request"

    return f"""\
Here's my **plan** before touching any code{focus}.

**Goal:** {prompt}

**Steps**
1. Inspect the relevant files and summarize the current behavior.
2. Draft the change and show a diff for review.
3. Run the affected tests and report results.

Example of the kind of edit I'd propose:

```python
def forge(component: str) -> str:
    \"\"\"Shape raw requirements into working software.\"\"\"
    return f"heated {{component}} -> hammered -> quenched"
```

> This is a mock response. Connect the internal AI API (TASK 3) to get real,
> context-aware plans. Nothing has been changed on disk."""


async def _stream_reply(text: str, delay: float) -> AsyncIterator[bytes]:
    for token in _TOKENIZER.findall(text):
        payload = json.dumps({"delta": token})
        yield f"data: {payload}\n\n".encode()
        if delay:
            await asyncio.sleep(delay)
    yield b"data: [DONE]\n\n"


async def _stream_real(config, request: ChatRequest) -> AsyncIterator[bytes]:
    """Stream a real assistant reply from the internal AI API (SUBTASK 3.2).

    Routes the request to a model (SUBTASK 3.4), emits an SSE meta event with the
    chosen model, then streams deltas. AI failures surface as a user-safe message
    delta (SUBTASK 3.3) rather than crashing the stream.
    """
    # Imported lazily to avoid a circular import (routing/ai_client import ChatRequest).
    from app.ai_client import AIClient, AIError, to_anthropic_messages
    from app.routing import route

    tier, model = route(config, request)
    logger.info("chat: routed tier=%s model=%s module=%s", tier, model, request.module)
    yield f"data: {json.dumps({'model': model, 'tier': tier})}\n\n".encode()

    client = AIClient(config)
    try:
        async for text in client.stream(to_anthropic_messages(request.messages), model=model):
            yield f"data: {json.dumps({'delta': text})}\n\n".encode()
    except AIError as exc:
        yield f"data: {json.dumps({'delta': f'⚠️ {exc}'})}\n\n".encode()
    finally:
        await client.aclose()
    yield b"data: [DONE]\n\n"


@router.post("/api/chat")
async def chat(request: ChatRequest, http_request: Request) -> StreamingResponse:
    """Stream an assistant reply as SSE — real AI when configured, else a mock."""
    config = http_request.app.state.config
    if config.ai.configured:
        generator = _stream_real(config, request)
    else:
        generator = _stream_reply(build_mock_reply(request), _STREAM_DELAY_S)
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
