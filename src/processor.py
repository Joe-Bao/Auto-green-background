from __future__ import annotations

from pathlib import Path
from typing import Iterable

import cv2
import numpy as np


def validate_threshold(threshold: int) -> None:
    if not 0 <= threshold <= 255:
        raise ValueError("threshold must be within 0..255")


def validate_target_size(target_width: int, target_height: int) -> None:
    if target_width <= 0 or target_height <= 0:
        raise ValueError("target width and height must be positive integers")


def validate_pad_color(pad_color: Iterable[int]) -> tuple[int, int, int]:
    color = tuple(int(c) for c in pad_color)
    if len(color) != 3:
        raise ValueError("pad color must contain 3 channel values")
    if any(c < 0 or c > 255 for c in color):
        raise ValueError("pad color channels must be within 0..255")
    return color  # type: ignore[return-value]


def create_binary_mask(img_gray: np.ndarray, threshold: int) -> np.ndarray:
    validate_threshold(threshold)
    _, mask = cv2.threshold(img_gray, threshold, 255, cv2.THRESH_BINARY)
    return mask


def create_border_grow_mask(
    img_gray: np.ndarray,
    background_threshold: int,
    max_iterations: int = 4096,
) -> np.ndarray:
    validate_threshold(background_threshold)
    if max_iterations < 1:
        raise ValueError("max iterations must be >= 1")

    # Start from image borders and recursively grow only through pixels
    # that satisfy the threshold rule.
    grow_candidate = img_gray >= background_threshold
    if not np.any(grow_candidate):
        return np.full_like(img_gray, 255, dtype=np.uint8)

    current = np.zeros_like(grow_candidate, dtype=bool)
    current[0, :] = grow_candidate[0, :]
    current[-1, :] = grow_candidate[-1, :]
    current[:, 0] = np.logical_or(current[:, 0], grow_candidate[:, 0])
    current[:, -1] = np.logical_or(current[:, -1], grow_candidate[:, -1])

    kernel = np.ones((3, 3), dtype=np.uint8)
    for _ in range(max_iterations):
        prev = current
        expanded = cv2.dilate(prev.astype(np.uint8), kernel, iterations=1).astype(bool)
        current = np.logical_and(expanded, grow_candidate)
        # Stop only when previous and next "frames" are unchanged.
        if np.array_equal(current, prev):
            break

    background_mask = current.astype(np.uint8) * 255
    foreground_mask = np.where(background_mask == 0, 255, 0).astype(np.uint8)
    return foreground_mask


def create_watershed_mask(
    img_color: np.ndarray,
    img_gray: np.ndarray,
    threshold: int,
    bg_tolerance: int = 12,
    border_width: int = 2,
    fg_seed_expand: int = 2,
) -> np.ndarray:
    validate_threshold(threshold)
    if bg_tolerance < 0:
        raise ValueError("background tolerance must be >= 0")
    if border_width < 1:
        raise ValueError("border width must be >= 1")
    if fg_seed_expand < 0:
        raise ValueError("foreground seed expand must be >= 0")

    h, w = img_gray.shape[:2]
    bw = min(border_width, max(1, min(h, w) // 4))

    border_samples = np.concatenate(
        [
            img_gray[:bw, :].ravel(),
            img_gray[-bw:, :].ravel(),
            img_gray[:, :bw].ravel(),
            img_gray[:, -bw:].ravel(),
        ]
    )
    bg_level = int(np.median(border_samples))

    sure_fg = (img_gray >= threshold).astype(np.uint8) * 255
    if fg_seed_expand > 0:
        fg_kernel = np.ones((fg_seed_expand * 2 + 1, fg_seed_expand * 2 + 1), dtype=np.uint8)
        sure_fg = cv2.dilate(sure_fg, fg_kernel, iterations=1)
    sure_bg = (np.abs(img_gray.astype(np.int16) - bg_level) <= bg_tolerance).astype(np.uint8) * 255
    sure_bg[:bw, :] = 255
    sure_bg[-bw:, :] = 255
    sure_bg[:, :bw] = 255
    sure_bg[:, -bw:] = 255
    sure_bg[sure_fg == 255] = 0

    markers = np.zeros((h, w), dtype=np.int32)
    markers[sure_bg == 255] = 1
    markers[sure_fg == 255] = 2

    ws_markers = cv2.watershed(img_color.copy(), markers)
    foreground = np.where(ws_markers == 2, 255, 0).astype(np.uint8)
    return foreground


def refine_mask_with_main_contour(
    mask: np.ndarray,
    morph_kernel_size: int = 1,
    contour_expand: int = 0,
) -> np.ndarray:
    if morph_kernel_size < 1 or morph_kernel_size % 2 == 0:
        raise ValueError("morph kernel size must be an odd integer >= 1")
    if contour_expand < 0:
        raise ValueError("contour expand must be >= 0")

    kernel = np.ones((morph_kernel_size, morph_kernel_size), dtype=np.uint8)
    cleaned = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return np.zeros_like(mask)

    main_contour = max(contours, key=cv2.contourArea)
    refined = np.zeros_like(mask)
    cv2.drawContours(refined, [main_contour], contourIdx=-1, color=255, thickness=-1)
    if contour_expand > 0:
        expand_kernel = np.ones((contour_expand * 2 + 1, contour_expand * 2 + 1), dtype=np.uint8)
        refined = cv2.dilate(refined, expand_kernel, iterations=1)
    return refined


def center_foreground_on_canvas(
    img_color: np.ndarray,
    mask: np.ndarray,
    target_width: int,
    target_height: int,
    pad_color: Iterable[int] = (0, 255, 0),
) -> np.ndarray:
    validate_target_size(target_width, target_height)
    color = validate_pad_color(pad_color)

    out = np.full((target_height, target_width, 3), color, dtype=img_color.dtype)
    ys, xs = np.where(mask > 0)
    if len(xs) == 0:
        return out

    y_min, y_max = ys.min(), ys.max()
    x_min, x_max = xs.min(), xs.max()

    alpha = (mask.astype(np.float32) / 255.0)[:, :, None]
    bg = np.full_like(img_color, color)
    fg_full = (img_color.astype(np.float32) * alpha + bg.astype(np.float32) * (1.0 - alpha)).astype(img_color.dtype)
    fg = fg_full[y_min : y_max + 1, x_min : x_max + 1]

    fg_h, fg_w = fg.shape[:2]
    if fg_h > target_height:
        start_y = (fg_h - target_height) // 2
        fg = fg[start_y : start_y + target_height, :]
        fg_h = target_height
    if fg_w > target_width:
        start_x = (fg_w - target_width) // 2
        fg = fg[:, start_x : start_x + target_width]
        fg_w = target_width

    dst_y = (target_height - fg_h) // 2
    dst_x = (target_width - fg_w) // 2
    out[dst_y : dst_y + fg_h, dst_x : dst_x + fg_w] = fg
    return out


def process_image_array(
    img_color: np.ndarray,
    threshold: int,
    target_width: int,
    target_height: int,
    pad_color: Iterable[int] = (0, 255, 0),
    refine_method: str = "watershed",
    morph_kernel_size: int = 1,
    contour_expand: int = 0,
    bg_tolerance: int = 12,
) -> np.ndarray:
    if img_color.ndim != 3 or img_color.shape[2] != 3:
        raise ValueError("input image must be a BGR color image")

    img_gray = cv2.cvtColor(img_color, cv2.COLOR_BGR2GRAY)
    mask = create_binary_mask(img_gray, threshold)
    method = refine_method.strip().lower()
    if method == "watershed":
        mask = create_watershed_mask(
            img_color=img_color,
            img_gray=img_gray,
            threshold=threshold,
            bg_tolerance=bg_tolerance,
            fg_seed_expand=contour_expand + 1,
        )
        mask = refine_mask_with_main_contour(
            mask,
            morph_kernel_size=morph_kernel_size,
            contour_expand=contour_expand,
        )
    elif method == "border-grow":
        mask = create_border_grow_mask(img_gray, background_threshold=threshold)
        mask = refine_mask_with_main_contour(
            mask,
            morph_kernel_size=morph_kernel_size,
            contour_expand=contour_expand,
        )
    elif method == "contour":
        mask = refine_mask_with_main_contour(
            mask,
            morph_kernel_size=morph_kernel_size,
            contour_expand=contour_expand,
        )
    elif method == "threshold":
        pass
    else:
        raise ValueError("refine method must be one of: threshold, contour, watershed, border-grow")

    return center_foreground_on_canvas(
        img_color=img_color,
        mask=mask,
        target_width=target_width,
        target_height=target_height,
        pad_color=pad_color,
    )


def process_image_file(
    input_path: str,
    output_path: str,
    threshold: int,
    target_width: int,
    target_height: int,
    pad_color: Iterable[int] = (0, 255, 0),
    refine_method: str = "watershed",
    morph_kernel_size: int = 1,
    contour_expand: int = 0,
    bg_tolerance: int = 12,
) -> np.ndarray:
    src = Path(input_path)
    if not src.exists():
        raise FileNotFoundError(f"input image not found: {input_path}")

    image = cv2.imread(str(src), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"failed to read image: {input_path}")

    result = process_image_array(
        img_color=image,
        threshold=threshold,
        target_width=target_width,
        target_height=target_height,
        pad_color=pad_color,
        refine_method=refine_method,
        morph_kernel_size=morph_kernel_size,
        contour_expand=contour_expand,
        bg_tolerance=bg_tolerance,
    )

    dst = Path(output_path)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(dst), result):
        raise ValueError(f"failed to write output image: {output_path}")
    return result
