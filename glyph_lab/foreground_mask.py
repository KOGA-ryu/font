from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image

from .ascii_glyph_renderer import _border_median_rgb, _rgb_distance


FOREGROUND_MODES = {"auto", "alpha", "background", "none"}


def foreground_mask(
    image: Image.Image,
    grid_width: int,
    grid_height: int,
    *,
    mode: str = "auto",
    alpha_threshold: int = 1,
    background_threshold: int = 28,
) -> tuple[list[list[bool]], dict[str, Any]]:
    if mode not in FOREGROUND_MODES:
        raise ValueError(f"unknown foreground mode {mode!r}; expected one of {sorted(FOREGROUND_MODES)}")
    if grid_width <= 0 or grid_height <= 0:
        raise ValueError("foreground grid size must be positive")
    if not 0 <= alpha_threshold <= 255:
        raise ValueError("foreground alpha threshold must be between 0 and 255")
    if background_threshold < 0:
        raise ValueError("foreground background threshold must be non-negative")

    rgba = image.convert("RGBA")
    resolved_mode = _resolve_mode(rgba, mode)
    if resolved_mode == "none":
        mask = [[True for _ in range(grid_width)] for _ in range(grid_height)]
        return mask, _summary(resolved_mode, alpha_threshold, background_threshold, None, mask)
    if resolved_mode == "alpha":
        sampled = rgba.resize((grid_width, grid_height), Image.Resampling.BOX)
        pixels = sampled.load()
        mask = [[pixels[x, y][3] > alpha_threshold for x in range(grid_width)] for y in range(grid_height)]
        return mask, _summary(resolved_mode, alpha_threshold, background_threshold, None, mask)

    sampled = rgba.resize((grid_width, grid_height), Image.Resampling.BOX)
    background = _border_median_rgb(sampled)
    pixels = sampled.load()
    mask = [
        [_rgb_distance(pixels[x, y][:3], background) > background_threshold for x in range(grid_width)]
        for y in range(grid_height)
    ]
    return mask, _summary(resolved_mode, alpha_threshold, background_threshold, background, mask)


def write_foreground_mask(mask: list[list[bool]], output_path: str | Path, *, scale: int = 1) -> None:
    height = len(mask)
    width = len(mask[0]) if height else 0
    image = Image.new("L", (width, height), 0)
    pixels = image.load()
    for y, row in enumerate(mask):
        for x, value in enumerate(row):
            pixels[x, y] = 255 if value else 0
    if scale > 1:
        image = image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)


def mask_and(left: list[list[bool]], right: list[list[bool]]) -> list[list[bool]]:
    if len(left) != len(right) or (left and len(left[0]) != len(right[0])):
        raise ValueError("foreground mask dimensions must match layer mask dimensions")
    return [[value and right[y][x] for x, value in enumerate(row)] for y, row in enumerate(left)]


def _resolve_mode(image: Image.Image, requested: str) -> str:
    if requested != "auto":
        return requested
    alpha = image.getchannel("A")
    if alpha.getextrema()[0] < 255:
        return "alpha"
    return "background"


def _summary(
    mode: str,
    alpha_threshold: int,
    background_threshold: int,
    background: tuple[int, int, int] | None,
    mask: list[list[bool]],
) -> dict[str, Any]:
    kept = sum(1 for row in mask for value in row if value)
    total = sum(len(row) for row in mask)
    return {
        "mode": mode,
        "alpha_threshold": alpha_threshold,
        "background_threshold": background_threshold,
        "background_rgb": list(background) if background is not None else None,
        "kept_cells": kept,
        "blank_cells": total - kept,
    }
