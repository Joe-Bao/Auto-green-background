from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.processor import process_image_file, validate_target_size, validate_threshold


def run_cli(args: argparse.Namespace) -> None:
    if not args.input or not args.output:
        raise ValueError("--input and --output are required in cli mode")

    validate_threshold(args.threshold)
    validate_target_size(args.width, args.height)
    process_image_file(
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
    print(f"Saved: {Path(args.output).resolve()}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Auto green background tool")
    parser.add_argument("--mode", choices=["gui", "cli"], default="gui")
    parser.add_argument("--input", help="Input image path (cli mode)")
    parser.add_argument("--output", help="Output image path (cli mode)")
    parser.add_argument("--threshold", type=int, default=250, help="Threshold 0..255")
    parser.add_argument("--width", type=int, default=40, help="Target canvas width")
    parser.add_argument("--height", type=int, default=40, help="Target canvas height")
    parser.add_argument(
        "--refine-method",
        choices=["threshold", "contour", "watershed", "border-grow"],
        default="watershed",
        help="Foreground refine method",
    )
    parser.add_argument(
        "--morph-kernel-size",
        type=int,
        default=1,
        help="Odd kernel size for morphology in contour mode",
    )
    parser.add_argument(
        "--contour-expand",
        type=int,
        default=0,
        help="Expand contour outward by N pixels to preserve dark outlines",
    )
    parser.add_argument(
        "--bg-tolerance",
        type=int,
        default=12,
        help="Background tolerance around border median for watershed mode",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.mode == "cli":
        run_cli(args)
        return

    if sys.version_info >= (3, 14):
        raise RuntimeError(
            "GUI mode requires Python < 3.14 because pywebview on Windows depends on pythonnet "
            "which does not support Python 3.14 yet. Use uv-managed Python 3.13 "
            "(run: `uv python install 3.13` then `uv sync`)."
        )

    from src.gui import launch_gui

    launch_gui()


if __name__ == "__main__":
    main()
