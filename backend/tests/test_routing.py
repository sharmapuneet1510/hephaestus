"""Tests for model routing (SUBTASK 3.4)."""

from __future__ import annotations

import pytest

from app.chat import ChatRequest
from app.config import load_config
from app.routing import classify, route, select_model


def _req(text: str, module: str | None = None) -> ChatRequest:
    return ChatRequest(messages=[{"role": "user", "content": text}], module=module)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Refactor the auth module into smaller services", "strong"),
        ("Design a system for multi-file migration across the codebase", "strong"),
        ("What is this function doing?", "simple"),
        ("Explain the login flow", "simple"),
        ("Add input validation to the login form and write a test", "medium"),
    ],
)
def test_classify_examples(text, expected):
    assert classify(_req(text)) == expected


def test_long_explain_prompt_is_not_simple():
    """A long prompt that merely starts with 'explain' should route to medium."""
    text = "explain " + " ".join(f"word{i}" for i in range(40))
    assert classify(_req(text)) == "medium"


def test_select_model_maps_tier_to_config():
    config = load_config(environ={})
    tiers = config.model_routing.tiers
    assert select_model(config, "simple") == tiers["simple"]
    assert select_model(config, "strong") == tiers["strong"]


def test_select_model_unknown_tier_falls_back_to_default():
    config = load_config(environ={})
    default_model = config.model_routing.tiers[config.model_routing.default_tier]
    assert select_model(config, "nonexistent") == default_model


def test_route_returns_tier_and_model():
    config = load_config(environ={})
    tier, model = route(config, _req("Refactor the whole repo architecture"))
    assert tier == "strong"
    assert model == config.model_routing.tiers["strong"]
