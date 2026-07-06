"""Hephaestus backend entrypoint (SUBTASK 1.1 / 1.4).

Creates the FastAPI application, loads configuration on startup (logging a
non-secret summary — SUBTASK 1.2 test), configures CORS for the Vite dev server,
and exposes a health endpoint the frontend uses to confirm connectivity.
"""

from __future__ import annotations

import logging

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import AppConfig, ConfigError, load_config

logger = logging.getLogger("hephaestus")


def create_app(config: AppConfig | None = None) -> FastAPI:
    """Application factory. Accepts an injected config for testing."""
    # Load .env (if present) before reading configuration so ${ENV} placeholders
    # and the API key resolve. Real env vars always win over .env.
    load_dotenv()

    if config is None:
        config = load_config()

    logging.basicConfig(level=logging.INFO)
    logger.info("Hephaestus backend v%s starting", __version__)
    logger.info("Active config: %s", config.summary())
    if not config.ai.configured:
        logger.warning(
            "AI is not configured — set HEPHAESTUS_AI_ENDPOINT and %s to enable "
            "assistant requests (see .env.example).",
            config.ai.api_key_env,
        )

    app = FastAPI(title="Hephaestus", version=__version__)
    app.state.config = config

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.server.cors_origins or ["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict:
        """Backend health check consumed by the frontend startup screen."""
        cfg: AppConfig = app.state.config
        return {
            "status": "ok",
            "service": "hephaestus-backend",
            "version": __version__,
            "ai_configured": cfg.ai.configured,
            "config": cfg.summary(),
        }

    return app


# Module-level app for `uvicorn app.main:app`.
try:
    app = create_app()
except ConfigError as exc:  # pragma: no cover - surfaced at process start
    logger.error("Startup failed: %s", exc)
    raise
