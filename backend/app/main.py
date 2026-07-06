"""Hephaestus backend entrypoint (SUBTASK 1.1 / 1.4).

Creates the FastAPI application, loads configuration on startup (logging a
non-secret summary — SUBTASK 1.2 test), configures CORS for the Vite dev server,
and exposes a health endpoint the frontend uses to confirm connectivity.
"""

from __future__ import annotations

import logging
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.chat import router as chat_router
from app.config import AppConfig, ConfigError, load_config
from app.context import default_context_engine
from app.context import router as context_router
from app.edit import default_edit_session
from app.edit import router as edit_router
from app.plan import default_plan_state
from app.plan import router as plan_router
from app.repo import default_session_store
from app.repo import router as repo_router

# Built frontend (produced by `npm run build`). When present, the backend serves
# it single-origin so no dev proxy is needed — the production deployment shape.
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"

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
    app.state.session_store = default_session_store()
    app.state.context_engine = default_context_engine()
    app.state.plan_state = default_plan_state()
    app.state.edit_session = default_edit_session()

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

    app.include_router(chat_router)
    app.include_router(repo_router)
    app.include_router(context_router)
    app.include_router(plan_router)
    app.include_router(edit_router)

    # Mounted last so it only catches non-API paths. Serves the built SPA when
    # available; harmless (skipped) during tests/dev when dist doesn't exist.
    if FRONTEND_DIST.is_dir():
        app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")

    return app


# Module-level app for `uvicorn app.main:app`.
try:
    app = create_app()
except ConfigError as exc:  # pragma: no cover - surfaced at process start
    logger.error("Startup failed: %s", exc)
    raise
