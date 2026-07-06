"""Tests for configuration loading and env handling (SUBTASK 1.2 / 1.3)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from app.config import ConfigError, load_config


def _write_config(tmp_path: Path) -> Path:
    """A minimal config mirroring the real default.yaml env-substitution shape."""
    cfg = tmp_path / "default.yaml"
    cfg.write_text(textwrap.dedent("""
            server:
              host: 127.0.0.1
              port: 8000
              cors_origins:
                - http://localhost:5173
            ai:
              endpoint: ${HEPHAESTUS_AI_ENDPOINT}
              api_key_env: HEPHAESTUS_AI_API_KEY
              timeout_seconds: 60
            model_routing:
              default_tier: medium
              tiers:
                simple: claude-haiku-4-5
                medium: claude-sonnet-5
                strong: claude-opus-4-8
            ignore_paths:
              - .git
              - node_modules
            test_commands:
              python: pytest
            """))
    return cfg


def test_loads_default_config_from_repo():
    """The real config/default.yaml loads and parses (SUBTASK 1.2)."""
    config = load_config(environ={})
    assert config.server.port == 8000
    assert config.model_routing.tiers["strong"] == "claude-opus-4-8"
    assert ".git" in config.ignore_paths
    assert config.test_commands["python"] == "pytest"


def test_env_substitution_and_api_key_resolution(tmp_path):
    """${VAR} placeholders and the API key resolve from the environment."""
    cfg = _write_config(tmp_path)
    env = {
        "HEPHAESTUS_AI_ENDPOINT": "https://ai.example.com/v1",
        "HEPHAESTUS_AI_API_KEY": "secret-key",
    }
    config = load_config(config_path=cfg, environ=env)
    assert config.ai.endpoint == "https://ai.example.com/v1"
    assert config.ai.api_key == "secret-key"
    assert config.ai.configured is True


def test_missing_env_leaves_none_not_placeholder(tmp_path):
    """Unset ${VAR} resolves to None, and the API key is None (SUBTASK 1.3)."""
    cfg = _write_config(tmp_path)
    config = load_config(config_path=cfg, environ={})
    assert config.ai.endpoint is None
    assert config.ai.api_key is None
    assert config.ai.configured is False


def test_require_ai_raises_clear_error_when_unset(tmp_path):
    """require_ai() names the exact missing env vars (SUBTASK 1.3)."""
    cfg = _write_config(tmp_path)
    config = load_config(config_path=cfg, environ={})
    with pytest.raises(ConfigError) as exc:
        config.require_ai()
    message = str(exc.value)
    assert "HEPHAESTUS_AI_ENDPOINT" in message
    assert "HEPHAESTUS_AI_API_KEY" in message


def test_require_ai_passes_when_configured(tmp_path):
    cfg = _write_config(tmp_path)
    env = {
        "HEPHAESTUS_AI_ENDPOINT": "https://ai.example.com/v1",
        "HEPHAESTUS_AI_API_KEY": "secret-key",
    }
    config = load_config(config_path=cfg, environ=env)
    assert config.require_ai() is config


def test_missing_config_file_raises(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(config_path=tmp_path / "does_not_exist.yaml", environ={})


def test_summary_excludes_secret_key(tmp_path):
    """The health/log summary never leaks the API key."""
    cfg = _write_config(tmp_path)
    env = {
        "HEPHAESTUS_AI_ENDPOINT": "https://ai.example.com/v1",
        "HEPHAESTUS_AI_API_KEY": "super-secret",
    }
    config = load_config(config_path=cfg, environ=env)
    summary_text = str(config.summary())
    assert "super-secret" not in summary_text
    assert config.summary()["ai_configured"] is True
