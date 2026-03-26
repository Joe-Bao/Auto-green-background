from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import cv2

from src.processor import process_image_array, process_image_file, validate_target_size, validate_threshold

try:
    import webview
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("pywebview is required for GUI mode. Install dependencies first.") from exc


def _to_data_url_png(image) -> str:
    ok, buf = cv2.imencode(".png", image)
    if not ok:
        raise ValueError("failed to encode preview image")
    encoded = base64.b64encode(buf.tobytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


class GreenScreenApi:
    def __init__(self) -> None:
        self.window: webview.Window | None = None

    def attach_window(self, window: webview.Window) -> None:
        self.window = window

    def select_input_file(self) -> str:
        if self.window is None:
            return ""
        files = self.window.create_file_dialog(
            webview.FileDialog.OPEN,
            allow_multiple=False,
            file_types=("Image files (*.png;*.jpg;*.jpeg;*.bmp;*.webp)",),
        )
        if not files:
            return ""
        return str(files[0])

    def select_output_file(self, suggested_name: str) -> str:
        if self.window is None:
            return ""
        files = self.window.create_file_dialog(
            webview.FileDialog.SAVE,
            save_filename=suggested_name,
            file_types=("PNG (*.png)",),
        )
        if not files:
            return ""
        return str(files[0])

    def _parse_params(
        self,
        threshold: Any,
        width: Any,
        height: Any,
        refine_method: Any,
        morph_kernel_size: Any,
        contour_expand: Any,
        bg_tolerance: Any,
    ) -> tuple[int, int, int, str, int, int, int]:
        t = int(threshold)
        w = int(width)
        h = int(height)
        method = str(refine_method).strip().lower()
        morph = int(morph_kernel_size)
        expand = int(contour_expand)
        bg_tol = int(bg_tolerance)
        validate_threshold(t)
        validate_target_size(w, h)
        if method not in {"threshold", "contour", "watershed", "border-grow"}:
            raise ValueError("refine method must be threshold, contour, watershed, or border-grow")
        if morph < 1 or morph % 2 == 0:
            raise ValueError("morph kernel size must be an odd integer >= 1")
        if expand < 0:
            raise ValueError("contour expand must be >= 0")
        if bg_tol < 0:
            raise ValueError("background tolerance must be >= 0")
        return t, w, h, method, morph, expand, bg_tol

    def preview(
        self,
        input_path: str,
        threshold: Any,
        width: Any,
        height: Any,
        refine_method: Any,
        morph_kernel_size: Any,
        contour_expand: Any,
        bg_tolerance: Any,
    ) -> dict[str, Any]:
        if not input_path:
            return {"ok": False, "error": "Please select an input image."}
        try:
            t, w, h, method, morph, expand, bg_tol = self._parse_params(
                threshold,
                width,
                height,
                refine_method,
                morph_kernel_size,
                contour_expand,
                bg_tolerance,
            )
            image = cv2.imread(input_path, cv2.IMREAD_COLOR)
            if image is None:
                return {"ok": False, "error": "Failed to read the input image."}
            result = process_image_array(
                img_color=image,
                threshold=t,
                target_width=w,
                target_height=h,
                refine_method=method,
                morph_kernel_size=morph,
                contour_expand=expand,
                bg_tolerance=bg_tol,
            )
            return {"ok": True, "preview": _to_data_url_png(result)}
        except Exception as exc:  # pragma: no cover
            return {"ok": False, "error": str(exc)}

    def process_and_save(
        self,
        input_path: str,
        output_path: str,
        threshold: Any,
        width: Any,
        height: Any,
        refine_method: Any,
        morph_kernel_size: Any,
        contour_expand: Any,
        bg_tolerance: Any,
    ) -> dict[str, Any]:
        if not input_path:
            return {"ok": False, "error": "Please select an input image."}
        if not output_path:
            return {"ok": False, "error": "Please select an output path."}
        try:
            t, w, h, method, morph, expand, bg_tol = self._parse_params(
                threshold,
                width,
                height,
                refine_method,
                morph_kernel_size,
                contour_expand,
                bg_tolerance,
            )
            result = process_image_file(
                input_path=input_path,
                output_path=output_path,
                threshold=t,
                target_width=w,
                target_height=h,
                refine_method=method,
                morph_kernel_size=morph,
                contour_expand=expand,
                bg_tolerance=bg_tol,
            )
            return {"ok": True, "output_path": str(Path(output_path).resolve()), "preview": _to_data_url_png(result)}
        except Exception as exc:  # pragma: no cover
            return {"ok": False, "error": str(exc)}


def launch_gui() -> None:
    html_path = Path(__file__).resolve().parent.parent / "web" / "index.html"
    api = GreenScreenApi()
    window = webview.create_window(
        title="Auto Green Background",
        url=html_path.as_uri(),
        js_api=api,
        width=980,
        height=760,
    )
    api.attach_window(window)
    webview.start()
