"""Configuration loading for Hephaestus (SUBTASK 1.2 / 1.3).

Loads ``config/default.yaml``, substitutes ``${ENV_VAR}`` placeholders from the
environment, and exposes a typed :class:`AppConfig`. Secrets (the AI API key)
are read from the environment by name and never stored in the YAML.

Design notes
------------
* The backend must boot and serve health checks *without* a real AI key, so AI
  configuration is validated lazily: :meth:`AppConfig.require_ai` raises a clear
  :class:`ConfigError` only when an AI call is actually attempted.
* ``${VAR}`` placeholders that resolve to nothing become ``None`` (not the empty
  string) so missing values are easy to detect and report.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Mapping, Optional

import yaml
from pydantic import BaseModel, Field

# Repo root = two levels up from this file (backend/app/config.py -> repo root).
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "default.yaml"

_ENV_PLACEHOLDER = re.compile(r"\$\{([A-Z0-9_]+)\}")


class ConfigError(RuntimeError):
    """Raised when configuration or required environment values are invalid."""


# --------------------------------------------------------------------------- #
# Typed config models (mirror config/default.yaml).
# --------------------------------------------------------------------------- #
class ServerConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: list[str] = Field(default_factory=list)


class AIConfig(BaseModel):
    endpoint: Optional[str] = None
    api_key_env: str = "HEPHAESTUS_AI_API_KEY"
    timeout_seconds: int = 60
    # Max output tokens per assistant reply (distinct from context.max_tokens).
    max_output_tokens: int = 4096
    # Resolved from ``os.environ[api_key_env]`` at load time; never from YAML.
    api_key: Optional[str] = None

    @property
    def configured(self) -> bool:
        """True when both an endpoint and an API key are present."""
        return bool(self.endpoint) and bool(self.api_key)


class ModelRoutingConfig(BaseModel):
    default_tier: str = "medium"
    tiers: dict[str, str] = Field(default_factory=dict)


class ContextConfig(BaseModel):
    max_tokens: int = 128000
    chunk_size_lines: int = 400
    cache_dir: str = ".hephaestus/cache"


class SafetyConfig(BaseModel):
    workspace_only: bool = True
    block_destructive: bool = True
    blocked_command_patterns: list[str] = Field(default_factory=list)
    confirm_command_patterns: list[str] = Field(default_factory=list)


class TasksConfig(BaseModel):
    task_file: str = "tasklist.txt"


class ClaudeMdConfig(BaseModel):
    path: str = "CLAUDE.md"
    update_after_task: bool = True


class AppConfig(BaseModel):
    server: ServerConfig = Field(default_factory=ServerConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    model_routing: ModelRoutingConfig = Field(default_factory=ModelRoutingConfig)
    context: ContextConfig = Field(default_factory=ContextConfig)
    ignore_paths: list[str] = Field(default_factory=list)
    test_commands: dict[str, str] = Field(default_factory=dict)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    tasks: TasksConfig = Field(default_factory=TasksConfig)
    claude_md: ClaudeMdConfig = Field(default_factory=ClaudeMdConfig)

    def require_ai(self) -> "AppConfig":
        """Ensure AI is configured, else raise a clear, actionable error.

        Called at the point an AI request is made (SUBTASK 1.3: missing required
        env values produce clear error messages).
        """
        missing: list[str] = []
        if not self.ai.endpoint:
            missing.append("HEPHAESTUS_AI_ENDPOINT (AI API base URL)")
        if not self.ai.api_key:
            missing.append(f"{self.ai.api_key_env} (AI API key)")
        if missing:
            raise ConfigError(
                "AI is not configured. Set the following environment variable(s) "
                "in your .env (see .env.example): " + ", ".join(missing)
            )
        return self

    def summary(self) -> dict[str, Any]:
        """Non-secret snapshot for health checks and dev startup logs."""
        return {
            "server": {"host": self.server.host, "port": self.server.port},
            "ai_configured": self.ai.configured,
            "ai_endpoint_set": bool(self.ai.endpoint),
            "model_tiers": self.model_routing.tiers,
            "default_tier": self.model_routing.default_tier,
            "ignore_paths": self.ignore_paths,
            "context_max_tokens": self.context.max_tokens,
        }


# --------------------------------------------------------------------------- #
# Loading + env substitution.
# --------------------------------------------------------------------------- #
def _substitute_env(value: Any, environ: Mapping[str, str]) -> Any:
    """Recursively replace ``${VAR}`` placeholders in strings.

    A placeholder whose variable is unset resolves to ``None`` when it is the
    entire string, or to an empty span when embedded, so missing values surface
    as ``None`` rather than a literal ``${VAR}``.
    """
    if isinstance(value, dict):
        return {k: _substitute_env(v, environ) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute_env(v, environ) for v in value]
    if isinstance(value, str):
        match = _ENV_PLACEHOLDER.fullmatch(value.strip())
        if match:
            # Whole-string placeholder -> preserve None for "unset".
            return environ.get(match.group(1)) or None
        return _ENV_PLACEHOLDER.sub(lambda m: environ.get(m.group(1), ""), value)
    return value


def load_config(
    config_path: Optional[Path | str] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> AppConfig:
    """Load and validate configuration.

    Parameters
    ----------
    config_path:
        Path to the YAML config. Defaults to ``config/default.yaml`` at the repo
        root, overridable via the ``HEPHAESTUS_CONFIG`` env var.
    environ:
        Environment mapping (defaults to ``os.environ``). Injected for testing.
    """
    environ = os.environ if environ is None else environ

    path = (
        Path(config_path)
        if config_path
        else Path(environ.get("HEPHAESTUS_CONFIG", DEFAULT_CONFIG_PATH))
    )
    if not path.is_file():
        raise ConfigError(f"Config file not found: {path}")

    try:
        raw = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:  # pragma: no cover - defensive
        raise ConfigError(f"Failed to parse config {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError(f"Config root must be a mapping, got {type(raw).__name__}")

    resolved = _substitute_env(raw, environ)

    # Resolve the API key from the env var named in the config.
    ai_section = resolved.get("ai") or {}
    api_key_env = ai_section.get("api_key_env", "HEPHAESTUS_AI_API_KEY")
    ai_section["api_key"] = environ.get(api_key_env) or None
    resolved["ai"] = ai_section

    try:
        return AppConfig(**resolved)
    except Exception as exc:  # pydantic ValidationError -> clear message
        raise ConfigError(f"Invalid configuration in {path}: {exc}") from exc
