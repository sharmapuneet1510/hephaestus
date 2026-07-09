# Icons

Tauri needs app icons here (`32x32.png`, `128x128.png`, `icon.icns`, `icon.ico`, …)
before `npm run tauri build`. Generate them from a single square PNG (≥ 512×512):

```bash
cd frontend
npm run tauri icon path/to/logo.png
```

This populates this directory. Icons are gitignored-friendly to commit if you like,
but they are not required for `npm run tauri dev`.
