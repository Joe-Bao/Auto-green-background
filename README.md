# Auto Green Background

Desktop tool for automatic green-screen compositing:

- Adjustable threshold (`0..255`)
- Fixed output canvas size (`width x height`)
- Foreground centered on green background
- No scaling; center-crop only when foreground exceeds canvas size

## Setup (uv)

```bash
uv python install 3.13
uv sync
```

`pywebview` on Windows currently relies on `pythonnet`, so Python 3.14 is not supported yet for GUI mode.

## CI/CD

- CI: GitHub Actions runs unit tests on push and pull requests (`.github/workflows/ci.yml`).
- CD: pushing a tag like `v0.1.0` triggers release pipeline (`.github/workflows/release.yml`):
  - run tests
  - build standalone Windows executable (PyInstaller)
  - upload `AutoGreenBackground-windows-x64.zip` to GitHub Release

## Run GUI

```bash
uv run python -m src.app --mode gui
```

## Run CLI

```bash
uv run python -m src.app --mode cli --input input.png --output output.png --threshold 250 --width 40 --height 40
```
