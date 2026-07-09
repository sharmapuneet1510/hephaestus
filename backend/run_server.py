"""Standalone backend entrypoint for the desktop sidecar (see DESKTOP.md).

Runs the FastAPI app on 127.0.0.1:8899. Used both as a convenient dev launcher
(`python run_server.py`) and as the PyInstaller entrypoint for the Tauri sidecar.
"""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    port = int(os.environ.get("HEPHAESTUS_PORT", "8899"))
    uvicorn.run("app.main:app", host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
