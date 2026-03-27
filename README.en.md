# Auto Green Background

[中文 README](./README.md)

Automatic green-screen tool built with `Tauri + Vue + Python (OpenCV)`.  
It segments the foreground from an input image and outputs a fixed-size green background canvas, suitable for template matching workflows.

## Features

- Multiple segmentation methods: `watershed`, `border-grow`, `contour`, `threshold`
- Fixed output canvas (`width x height`) with centered foreground
- Realtime preview with throttling/coalescing to reduce UI stutter
- Bilingual UI and parameter tooltips (hover + click)
- Bundled Python runtime and dependencies (portable package, no Python install needed)

## Local Development

### 1) Python environment

```bash
uv python install 3.13
uv sync
```

### 2) Frontend and desktop app

```bash
npm install
npm --prefix frontend install
npm run tauri:dev
```

## Build & Package

### Portable package (recommended)

```bash
npm run tauri:build:portable
```

Output:

- `dist-portable/AutoGreenBackground-win-x64-v<version>-portable.zip`

Notes:

- `<version>` defaults to `src-tauri/tauri.conf.json`
- In CI/CD, it follows the git tag (for example `v0.1.0`)

## Performance Notes

- App startup prewarms the bridge process in background to reduce first-preview cold start
- Rust and Python communicate through a persistent bridge (long connection), not process-per-request
- Fast preview path supports downscale + JPEG transfer; final export keeps full-quality processing
- On Windows, background bridge process runs without showing a cmd window

## Optional CLI (Python)

```bash
uv run python -m src.app --mode cli --input input.png --output output.png --threshold 250 --width 40 --height 40
```

## CI/CD

- CI: `.github/workflows/ci.yml`
  - Python tests (Windows + Ubuntu)
  - Frontend build check
- CD: `.github/workflows/release.yml` (triggered by `v*` tags)
  - Builds portable zip
  - Uploads artifact to GitHub Release

Release example:

```bash
git tag v0.1.1
git push origin v0.1.1
```
