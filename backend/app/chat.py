"""Chat endpoint (TASK 2, subtasks 2.2 / 2.3).

Streams a **mock** assistant reply over Server-Sent Events. Real AI integration
arrives in TASK 3; until then this produces deterministic, plan-first markdown
(including fenced code blocks) so the UI's streaming and code rendering can be
built and tested end-to-end.

Wire protocol (OpenAI-style SSE): each event is ``data: {"delta": "..."}`` and
the stream terminates with ``data: [DONE]``.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from typing import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

router = APIRouter()

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


@router.post("/api/chat")
async def chat(request: ChatRequest) -> StreamingResponse:
    """Stream a mock assistant reply as SSE."""
    reply = build_mock_reply(request)
    return StreamingResponse(
        _stream_reply(reply, _STREAM_DELAY_S),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
