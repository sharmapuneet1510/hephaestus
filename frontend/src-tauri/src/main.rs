// Hephaestus desktop shell (Tauri v2).
//
// The window loads the local backend URL (the FastAPI backend serves the built
// SPA, exactly like the web version — so `/api` stays same-origin). The Tauri
// JS API (native folder dialog) is injected into that window via the `remote`
// capability in `capabilities/default.json`.
//
// Backend startup:
//   * Release: bundle the backend as a Tauri sidecar (`externalBin`, built with
//     PyInstaller — see DESKTOP.md) and this spawns it on launch.
//   * Dev: run `uvicorn app.main:app --port 8899` yourself; the sidecar lookup
//     fails gracefully and we assume a backend is already listening on :8899.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri_plugin_shell::ShellExt;

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            // Best-effort: start the bundled backend sidecar if present.
            match app.shell().sidecar("hephaestus-backend") {
                Ok(command) => {
                    if let Err(err) = command.spawn() {
                        eprintln!("Failed to spawn backend sidecar: {err}");
                    }
                }
                Err(err) => {
                    eprintln!(
                        "No bundled backend sidecar ({err}); \
                         assuming a backend is already running on http://127.0.0.1:8899"
                    );
                }
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running the Hephaestus desktop app");
}
