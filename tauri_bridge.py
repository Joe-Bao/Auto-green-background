from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from pathlib import Path

import cv2

# Ensure repository root is importable when script runs from resources dir.
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.processor import process_image_array, process_image_file  # noqa: E402

_IMAGE_CACHE: dict[str, object] = {
    "path": None,
    "mtime": None,
    "image": None,
}


def to_data_url(image, codec: str = "png", quality: int = 85) -> str:
    codec_name = codec.strip().lower()
    if codec_name in ("jpg", "jpeg"):
        ext = ".jpg"
        params = [int(cv2.IMWRITE_JPEG_QUALITY), int(max(1, min(100, quality)))]
        mime = "image/jpeg"
    else:
        ext = ".png"
        params = []
        mime = "image/png"

    ok, buf = cv2.imencode(ext, image, params)
    if not ok:
        raise ValueError("failed to encode preview image")
    encoded = base64.b64encode(buf.tobytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tauri bridge for image processing")
    parser.add_argument("--mode", choices=["preview", "process", "server"], required=True)
    parser.add_argument("--input")
    parser.add_argument("--output")
    parser.add_argument("--threshold", type=int, default=245)
    parser.add_argument("--width", type=int, default=40)
    parser.add_argument("--height", type=int, default=40)
    parser.add_argument("--refine-method", default="watershed")
    parser.add_argument("--morph-kernel-size", type=int, default=1)
    parser.add_argument("--contour-expand", type=int, default=0)
    parser.add_argument("--bg-tolerance", type=int, default=12)
    parser.add_argument("--fast-preview", type=int, default=0)
    parser.add_argument("--preview-max-side", type=int, default=0)
    parser.add_argument("--preview-codec", default="png")
    parser.add_argument("--preview-quality", type=int, default=85)
    return parser.parse_args()


def emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def _cached_read_image(input_path: str) -> cv2.typing.MatLike:
    path = Path(input_path)
    mtime = path.stat().st_mtime
    if _IMAGE_CACHE["path"] == str(path) and _IMAGE_CACHE["mtime"] == mtime and _IMAGE_CACHE["image"] is not None:
        return _IMAGE_CACHE["image"]  # type: ignore[return-value]

    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"failed to read image: {input_path}")
    _IMAGE_CACHE["path"] = str(path)
    _IMAGE_CACHE["mtime"] = mtime
    _IMAGE_CACHE["image"] = image
    return image


def _process_preview(
    input_path: str,
    threshold: int,
    width: int,
    height: int,
    refine_method: str,
    morph_kernel_size: int,
    contour_expand: int,
    bg_tolerance: int,
    fast_preview: bool,
    preview_max_side: int,
) -> cv2.typing.MatLike:
    image = _cached_read_image(input_path)
    return process_image_array(
        img_color=image,
        threshold=threshold,
        target_width=width,
        target_height=height,
        refine_method=refine_method,
        morph_kernel_size=morph_kernel_size,
        contour_expand=contour_expand,
        bg_tolerance=bg_tolerance,
        fast_preview=fast_preview,
        preview_max_side=preview_max_side,
    )


def _handle_request(req: dict) -> dict:
    req_id = str(req.get("id") or "")
    started = time.perf_counter()
    try:
        mode = str(req["mode"])
        input_path = str(req["input"])
        threshold = int(req["threshold"])
        width = int(req["width"])
        height = int(req["height"])
        refine_method = str(req["refine_method"])
        morph_kernel_size = int(req["morph_kernel_size"])
        contour_expand = int(req["contour_expand"])
        bg_tolerance = int(req["bg_tolerance"])
        fast_preview = bool(req.get("fast_preview", False))
        preview_max_side = int(req.get("preview_max_side", 0))
        preview_codec = str(req.get("preview_codec", "png"))
        preview_quality = int(req.get("preview_quality", 85))

        if mode == "preview":
            result = _process_preview(
                input_path=input_path,
                threshold=threshold,
                width=width,
                height=height,
                refine_method=refine_method,
                morph_kernel_size=morph_kernel_size,
                contour_expand=contour_expand,
                bg_tolerance=bg_tolerance,
                fast_preview=fast_preview,
                preview_max_side=preview_max_side,
            )
            return {
                "id": req_id,
                "ok": True,
                "preview": to_data_url(result, codec=preview_codec, quality=preview_quality),
                "elapsedMs": int((time.perf_counter() - started) * 1000),
            }

        if mode == "process":
            output_path = req.get("output")
            if not output_path:
                raise ValueError("output is required in process mode")
            result = process_image_file(
                input_path=input_path,
                output_path=str(output_path),
                threshold=threshold,
                target_width=width,
                target_height=height,
                refine_method=refine_method,
                morph_kernel_size=morph_kernel_size,
                contour_expand=contour_expand,
                bg_tolerance=bg_tolerance,
            )
            return {
                "id": req_id,
                "ok": True,
                "preview": to_data_url(result, codec="png"),
                "elapsedMs": int((time.perf_counter() - started) * 1000),
            }

        if mode == "shutdown":
            return {"id": req_id, "ok": True, "preview": "", "shutdown": True}
        raise ValueError(f"unsupported mode: {mode}")
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return {
            "id": req_id,
            "ok": False,
            "error": str(exc),
            "elapsedMs": int((time.perf_counter() - started) * 1000),
        }


def run_server() -> int:
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                raise ValueError("request must be an object")
        except Exception as exc:  # pylint: disable=broad-exception-caught
            emit({"id": "", "ok": False, "error": f"invalid request: {exc}"})
            continue

        response = _handle_request(request)
        emit(response)
        if response.get("shutdown"):
            break
    return 0


def main() -> int:
    args = parse_args()
    try:
        if args.mode == "server":
            return run_server()

        if not args.input:
            raise ValueError("--input is required in preview/process mode")

        if args.mode == "preview":
            result = _process_preview(
                input_path=args.input,
                threshold=args.threshold,
                width=args.width,
                height=args.height,
                refine_method=args.refine_method,
                morph_kernel_size=args.morph_kernel_size,
                contour_expand=args.contour_expand,
                bg_tolerance=args.bg_tolerance,
                fast_preview=bool(args.fast_preview),
                preview_max_side=args.preview_max_side,
            )
            emit(
                {
                    "id": "oneshot",
                    "ok": True,
                    "preview": to_data_url(result, codec=args.preview_codec, quality=args.preview_quality),
                }
            )
            return 0

        if not args.output:
            raise ValueError("--output is required in process mode")

        result = process_image_file(
            input_path=args.input,
            output_path=args.output,
            threshold=args.threshold,
            target_width=args.width,
            target_height=args.height,
            refine_method=args.refine_method,
            morph_kernel_size=args.morph_kernel_size,
            contour_expand=args.contour_expand,
            bg_tolerance=args.bg_tolerance,
        )
        emit({"id": "oneshot", "ok": True, "preview": to_data_url(result, codec="png")})
        return 0
    except Exception as exc:
        emit({"id": "oneshot", "ok": False, "error": str(exc)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
