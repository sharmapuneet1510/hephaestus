"""Reusable AI client (SUBTASK 3.1 / 3.3), independent of the UI.

Wraps the official Anthropic SDK (`anthropic.AsyncAnthropic`) pointed at the
internal AI API via ``base_url``. Exposes a single streaming method and maps the
SDK's typed exceptions to a domain :class:`AIError` carrying a user-safe message.

The internal endpoint is assumed to speak the Anthropic Messages API (the common
shape for internal LLM gateways). If it doesn't, only this module changes.
"""

from __future__ import annotations

import logging
from typing import AsyncIterator, Iterable, Optional

import anthropic
import httpx

from app.chat import ChatMessage
from app.config import AppConfig

logger = logging.getLogger("hephaestus.ai")

# Hephaestus's plan-first system prompt (mirrors CLAUDE_INSTRUCTIONS.md).
SYSTEM_PROMPT = (
    "You are Hephaestus, an internal AI coding assistant. Work plan-first: before "
    "proposing code changes, briefly state the goal, the files likely to change, a "
    "step-by-step approach, tests to run, and risks. Show diffs before applying edits, "
    "prefer minimal patches, preserve the project's existing style, and never claim a "
    "test passed without evidence. Keep responses concise but complete."
)


class AIError(RuntimeError):
    """A user-safe AI failure. ``str(err)`` is safe to show to end users."""

    def __init__(self, user_message: str, *, status: Optional[int] = None):
        super().__init__(user_message)
        self.status = status


def to_anthropic_messages(messages: Iterable[ChatMessage]) -> list[dict]:
    """Convert Hephaestus chat messages to the Anthropic messages format.

    Only ``user`` / ``assistant`` roles are valid in the messages array; any
    other role is coerced to ``user`` (the system prompt is passed separately).
    """
    converted: list[dict] = []
    for message in messages:
        role = message.role if message.role in ("user", "assistant") else "user"
        converted.append({"role": role, "content": message.content})
    return converted


def _map_error(exc: Exception) -> AIError:
    """Map an Anthropic SDK exception to a clear, user-safe :class:`AIError`."""
    if isinstance(exc, anthropic.APITimeoutError):
        return AIError("The AI request timed out. Please try again.")
    if isinstance(exc, anthropic.AuthenticationError):
        return AIError("AI authentication failed — check the configured API key.", status=401)
    if isinstance(exc, anthropic.PermissionDeniedError):
        return AIError("The configured API key lacks access to this model.", status=403)
    if isinstance(exc, anthropic.NotFoundError):
        return AIError("The AI model or endpoint was not found — check the config.", status=404)
    if isinstance(exc, anthropic.RateLimitError):
        return AIError("The AI API is rate limiting requests. Please retry shortly.", status=429)
    if isinstance(exc, anthropic.BadRequestError):
        return AIError("The AI request was rejected as invalid. Please rephrase.", status=400)
    if isinstance(exc, anthropic.APIConnectionError):
        # APITimeoutError is a subclass and is handled above.
        return AIError("Could not reach the AI API — check the endpoint and network.")
    if isinstance(exc, anthropic.APIStatusError):
        status = getattr(exc, "status_code", None)
        if status and status >= 500:
            return AIError("The AI API returned a server error. Please retry.", status=status)
        return AIError("The AI API returned an error. Please try again.", status=status)
    return AIError("An unexpected error occurred talking to the AI API.")


class AIClient:
    """Thin async wrapper over the Anthropic SDK for streaming chat completions."""

    def __init__(self, config: AppConfig, http_client: Optional[httpx.AsyncClient] = None):
        self.config = config
        self._client = anthropic.AsyncAnthropic(
            api_key=config.ai.api_key or "unset",
            base_url=config.ai.endpoint or None,
            timeout=config.ai.timeout_seconds,
            max_retries=1,
            http_client=http_client,
        )

    async def stream(
        self,
        messages: list[dict],
        *,
        model: str,
        system: str = SYSTEM_PROMPT,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[str]:
        """Stream an assistant reply as text deltas, mapping SDK errors to AIError."""
        max_tokens = max_tokens or self.config.ai.max_output_tokens
        try:
            async with self._client.messages.stream(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=messages,
            ) as stream:
                async for text in stream.text_stream:
                    yield text
        except anthropic.APIError as exc:
            logger.warning("AI request failed: %s", type(exc).__name__)
            raise _map_error(exc) from exc

    async def aclose(self) -> None:
        await self._client.close()
