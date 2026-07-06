"""Model routing (SUBTASK 3.4).

Classifies a chat request into a complexity tier, then maps the tier to a
concrete model from ``config.model_routing``. Keeping this pure and separate
from the AI client makes the routing decision easy to log, test, and override.
"""

from __future__ import annotations

from app.chat import ChatRequest
from app.config import AppConfig

Tier = str  # one of: "simple" | "medium" | "strong"

# Architecture / multi-file / large-context work -> strongest model.
_STRONG_SIGNALS = (
    "refactor",
    "architecture",
    "architect",
    "migrate",
    "migration",
    "multi-file",
    "multi file",
    "redesign",
    "rewrite",
    "system design",
    "design a",
    "across the codebase",
    "whole repo",
    "entire repo",
    "restructure",
)

# Small explain/format/lookup tasks -> fast, cheap model.
_SIMPLE_SIGNALS = (
    "explain",
    "what is",
    "what does",
    "what's",
    "format",
    "rename",
    "typo",
    "summarize",
    "summarise",
    "list ",
    "show me",
    "how do i",
)


def _last_user_text(request: ChatRequest) -> str:
    for message in reversed(request.messages):
        if message.role == "user":
            return message.content
    return ""


def classify(request: ChatRequest) -> Tier:
    """Classify a request as ``simple`` | ``medium`` | ``strong``.

    Heuristic and deliberately explainable: a module focus or architecture
    signal biases toward ``strong``; short lookup/explain prompts toward
    ``simple``; everything else is ``medium``.
    """
    text = _last_user_text(request).lower()
    word_count = len(text.split())

    if any(signal in text for signal in _STRONG_SIGNALS):
        return "strong"
    if any(signal in text for signal in _SIMPLE_SIGNALS) and word_count <= 24:
        return "simple"
    return "medium"


def select_model(config: AppConfig, tier: Tier) -> str:
    """Resolve a tier to a concrete model id from config, with a safe fallback."""
    tiers = config.model_routing.tiers
    model = tiers.get(tier)
    if model:
        return model
    # Fall back to the configured default tier, then to any available model.
    default = tiers.get(config.model_routing.default_tier)
    if default:
        return default
    if tiers:
        return next(iter(tiers.values()))
    raise ValueError("No models configured under model_routing.tiers")


def route(config: AppConfig, request: ChatRequest) -> tuple[Tier, str]:
    """Classify then select — the single entry point used by the chat endpoint."""
    tier = classify(request)
    return tier, select_model(config, tier)
