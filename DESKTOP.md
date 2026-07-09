# Hephaestus — Desktop app (Tauri)

Hephaestus ships in two forms:

1. **Web app** (default) — run the backend and open `http://127.0.0.1:8899`. You load a
   repo by pasting its path (a browser can't hand a real filesystem path to the backend).
2. **Desktop app** (this doc) — a Tauri v2 shell that wraps the same React UI + FastAPI
   backend and adds a **native "Open Folder" dialog** (real path → backend). Single window,
   no manual path typing.

Both share one codebase: the desktop window simply loads the local backend URL, so `/api`
stays same-origin. The only desktop-specific code is the native folder picker
(`isDesktop()` / `openFolderDialog()` in `frontend/src/api.ts`), which is hidden on the web.

## Prerequisites

- Everything the web app needs (Python 3.11+, Node 20+, the backend `.venv`).
- **Rust** (Tauri compiles a native shell): https://rustup.rs → `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`
- Platform webview deps: macOS needs Xcode Command Line Tools (`xcode-select --install`);
  Linux needs `libwebkit2gtk-4.1-dev` + `libgtk-3-dev` etc. (see tauri.app prerequisites).
- App icons (once): `cd frontend && npm run tauri icon path/to/logo.png` (≥512×512 PNG).

## Run in development

Two terminals — run the backend yourself, then launch the shell (its sidecar lookup fails
gracefully and it connects to the backend you started):

```bash
# Terminal 1 — backend on :8899
cd backend
.venv/bin/python -m uvicorn app.main:app --port 8899

# Terminal 2 — desktop shell (rebuilds the SPA, opens the native window)
cd frontend
npm run tauri dev
```

The window opens at `http://127.0.0.1:8899`; click **📁 Open…** to pick a repo folder natively.

## Build a self-contained installer

For a single installable app, bundle the backend as a Tauri **sidecar** so users don't need
Python. Build a standalone backend binary with PyInstaller, drop it in `binaries/` named for
your target triple, add it to `externalBin`, then bundle:

```bash
# 1. Build the backend into one binary (from backend/)
cd backend
.venv/bin/python -m pip install pyinstaller
.venv/bin/pyinstaller --onefile --name hephaestus-backend \
  --add-data "../config:config" \
  -p . run_server.py         # a tiny entrypoint that runs uvicorn on :8899

# 2. Place it where Tauri expects (rename with the Rust target triple)
TRIPLE=$(rustc -Vv | sed -n 's/host: //p')
mkdir -p ../frontend/src-tauri/binaries
cp dist/hephaestus-backend ../frontend/src-tauri/binaries/hephaestus-backend-$TRIPLE

# 3. Add the sidecar to tauri.conf.json → bundle.externalBin:
#      "externalBin": ["binaries/hephaestus-backend"]

# 4. Bundle the desktop app (.app/.dmg on macOS, .msi on Windows, .deb/.AppImage on Linux)
cd ../frontend
npm run tauri build
```

`src-tauri/src/main.rs` spawns that sidecar on launch, so the installed app starts its own
backend on `:8899` and opens the window — no separate terminal, no Python required on the
target machine.

## Layout

```
frontend/src-tauri/
  tauri.conf.json          # window (loads http://127.0.0.1:8899), bundle config
  Cargo.toml, build.rs     # Rust crate
  src/main.rs              # spawns the backend sidecar, then Tauri opens the window
  capabilities/default.json# grants the native dialog on the local-URL window
  icons/                   # generated via `npm run tauri icon`
```

> Note: the Rust shell is compiled on your machine (`npm run tauri dev|build`); it was not
> compiled in the environment that scaffolded it. If a Tauri v2 API name needs a tweak for your
> installed crate versions, the compiler error will point right at it.
