# Auto Green Background

Desktop app for automatic green-screen compositing with Tauri + Vue + Python image processing.

## Features

- Adjustable segmentation methods: `watershed`, `border-grow`, `contour`, `threshold`
- Fixed output canvas (`width x height`) with centered foreground
- Real-time preview with queue/coalescing
- Built-in tooltip guidance (Chinese/English i18n)
- Bundled Python runtime (portable package, no Python install required)

## Local Development

### Python environment

```bash
uv python install 3.13
uv sync
```

### Desktop app (Tauri)

```bash
npm install
npm --prefix frontend install
npm run tauri:dev
```

## Build & Package

### Installer build (MSI/NSIS)

```bash
npm run tauri:build
```

### Portable build (recommended for zero-install use)

```bash
npm run tauri:build:portable
```

Output:

- `dist-portable/AutoGreenBackground-win-x64-v<version>-portable.zip`

## Performance Notes

- App startup now prewarms the bridge process in background to reduce first-preview latency.
- Bridge runs in persistent server mode (long connection) instead of spawning process per preview.
- Fast preview path supports downscale + JPEG preview transfer; final save keeps full-quality pipeline.

## Optional CLI (Python only)

```bash
uv run python -m src.app --mode cli --input input.png --output output.png --threshold 250 --width 40 --height 40
```

## CI/CD

- CI: `.github/workflows/ci.yml`
  - Python unit tests (Windows + Ubuntu)
  - Frontend build check
- CD: `.github/workflows/release.yml` (triggered by tag push `v*`)
  - Build Windows installer bundles
  - Build portable zip package
  - Upload all artifacts to GitHub Release

Tag example:

```bash
git tag v0.1.1
git push origin v0.1.1
```
