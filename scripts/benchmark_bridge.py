from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import cv2
import numpy as np


def create_input_image(path: Path) -> None:
    image = np.full((600, 600, 3), 160, dtype=np.uint8)
    cv2.rectangle(image, (140, 140), (460, 460), (250, 250, 250), -1)
    cv2.rectangle(image, (120, 120), (480, 480), (92, 92, 92), 12)
    if not cv2.imwrite(str(path), image):
        raise RuntimeError(f"failed to create benchmark image: {path}")


def run_oneshot(python_exe: str, root: Path, image_path: Path) -> list[float]:
    args = [
        python_exe,
        str(root / "tauri_bridge.py"),
        "--mode",
        "preview",
        "--input",
        str(image_path),
        "--threshold",
        "235",
        "--width",
        "80",
        "--height",
        "80",
        "--refine-method",
        "contour",
        "--morph-kernel-size",
        "1",
        "--contour-expand",
        "0",
        "--bg-tolerance",
        "12",
        "--fast-preview",
        "1",
        "--preview-max-side",
        "720",
        "--preview-codec",
        "jpeg",
        "--preview-quality",
        "85",
    ]
    results: list[float] = []
    for _ in range(3):
        started = time.perf_counter()
        completed = subprocess.run(args, capture_output=True, text=True, timeout=30, check=True)
        json.loads(completed.stdout)
        results.append((time.perf_counter() - started) * 1000)
    return results


def run_server(python_exe: str, root: Path, image_path: Path) -> list[float]:
    proc = subprocess.Popen(
        [python_exe, str(root / "tauri_bridge.py"), "--mode", "server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    if proc.stdin is None or proc.stdout is None:
        raise RuntimeError("failed to open server stdio pipes")

    results: list[float] = []
    try:
        for i in range(3):
            request = {
                "id": str(i),
                "mode": "preview",
                "input": str(image_path),
                "threshold": 235,
                "width": 80,
                "height": 80,
                "refine_method": "contour",
                "morph_kernel_size": 1,
                "contour_expand": 0,
                "bg_tolerance": 12,
                "fast_preview": True,
                "preview_max_side": 720,
                "preview_codec": "jpeg",
                "preview_quality": 85,
            }
            started = time.perf_counter()
            proc.stdin.write(json.dumps(request) + "\n")
            proc.stdin.flush()
            line = proc.stdout.readline()
            if not line:
                raise RuntimeError(proc.stderr.read() if proc.stderr else "server closed without response")
            payload = json.loads(line)
            if not payload.get("ok"):
                raise RuntimeError(json.dumps(payload, ensure_ascii=False))
            results.append((time.perf_counter() - started) * 1000)
    finally:
        proc.terminate()
        proc.wait(timeout=5)
    return results


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    image_path = Path(tempfile.gettempdir()) / "bridge_benchmark_input.png"
    create_input_image(image_path)

    python_exe = sys.executable
    oneshot = run_oneshot(python_exe, root, image_path)
    server = run_server(python_exe, root, image_path)

    summary = {
        "oneshot_ms": oneshot,
        "oneshot_avg_ms": sum(oneshot) / len(oneshot),
        "server_ms": server,
        "server_avg_ms": sum(server) / len(server),
        "speedup_ratio": (sum(oneshot) / len(oneshot)) / (sum(server) / len(server)),
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
