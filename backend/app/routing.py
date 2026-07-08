"""Model routing (SUBTASK 3.4).

Classifies a chat request into a complexity tier, then maps the tier to a
concrete model from ``config.model_routing``. Keeping this pure and separate
from the AI client makes the routing decision easy to log, test, and override.
"""

from __future__ import annotations

from app.chat import ChatRequest
from app.config import AppConfig

Tier = str  # one of: "simple" | "medium" | "strong"

Category = str  # simple | medium | complex | architecture (SUBTASK 13.1)

# Architecture-level work — the highest tier.
_ARCHITECTURE_SIGNALS = (
    "architecture",
    "architect",
    "system design",
    "design a system",
    "microservice",
    "restructure",
    "across the codebase",
    "whole repo",
    "entire repo",
)

# Complex multi-file changes.
_COMPLEX_SIGNALS = (
    "refactor",
    "migrate",
    "migration",
    "multi-file",
    "multi file",
    "redesign",
    "rewrite",
    "design a",
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

# Category -> model tier.
_CATEGORY_TIER: dict[Category, Tier] = {
    "simple": "simple",
    "medium": "medium",
    "complex": "strong",
    "architecture": "strong",
}


def _last_user_text(request: ChatRequest) -> str:
    for message in reversed(request.messages):
        if message.role == "user":
            return message.content
    return ""


def classify_category(request: ChatRequest) -> Category:
    """Classify a request as simple | medium | complex | architecture (SUBTASK 13.1)."""
    text = _last_user_text(request).lower()
    word_count = len(text.split())

    if any(signal in text for signal in _ARCHITECTURE_SIGNALS):
        return "architecture"
    if any(signal in text for signal in _COMPLEX_SIGNALS):
        return "complex"
    if any(signal in text for signal in _SIMPLE_SIGNALS) and word_count <= 24:
        return "simple"
    return "medium"


def classify(request: ChatRequest) -> Tier:
    """Classify a request to a model tier (via its category)."""
    return _CATEGORY_TIER[classify_category(request)]


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
