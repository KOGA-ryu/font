from __future__ import annotations

from pathlib import Path
from statistics import mean
from typing import Any
import json

from PIL import Image, ImageDraw

from .contours import extract_contours
from .image_probe import auto_crop_non_background, load_luminance, mass_mask, sample_luminance_grid


def measure_profile(mask: list[list[bool]], crop_box: list[int] | None = None) -> dict[str, Any]:
    contours = extract_contours(mask)
    widths = contours["width_profile_by_row"]
    occupied_rows = [index for index, width in enumerate(widths) if width > 0]
    active_widths = [widths[index] for index in occupied_rows]
    grid_width = len(mask[0]) if mask else 0
    reference_centerline = (grid_width - 1) / 2 if grid_width else None

    if not active_widths:
        return {
            **contours,
            "crop_box": crop_box,
            "grid_size": [grid_width, len(mask)],
            "total_height_cells": 0,
            "max_width_cells": 0,
            "min_width_cells": 0,
            "average_width_cells": 0,
            "top_width": 0,
            "middle_width": 0,
            "bottom_width": 0,
            "taper_ratio": None,
            "symmetry_error": None,
            "row_width_variance": 0,
            "likely_shape": "unknown",
            "curved_profile": False,
            "bulge_rows": [],
            "neck_rows": [],
        }

    top_width = active_widths[0]
    middle_width = widths[occupied_rows[len(occupied_rows) // 2]]
    bottom_width = active_widths[-1]
    average_width = mean(active_widths)
    variance = mean((width - average_width) ** 2 for width in active_widths)
    bulge_rows, neck_rows = _curve_rows(widths, occupied_rows)
    measurement = {
        **contours,
        "crop_box": crop_box,
        "grid_size": [grid_width, len(mask)],
        "total_height_cells": len(occupied_rows),
        "max_width_cells": max(active_widths),
        "min_width_cells": min(active_widths),
        "average_width_cells": round(average_width, 4),
        "top_width": top_width,
        "middle_width": middle_width,
        "bottom_width": bottom_width,
        "taper_ratio": round(top_width / bottom_width, 4) if bottom_width else None,
        "symmetry_error": _symmetry_error(contours, occupied_rows, reference_centerline),
        "row_width_variance": round(variance, 4),
        "bulge_rows": bulge_rows,
        "neck_rows": neck_rows,
    }
    measurement["curved_profile"] = _is_smoothly_curved(widths, occupied_rows)
    measurement["likely_shape"] = classify_shape(measurement)
    return measurement


def measure_profile_image(
    image_path: str | Path,
    output_dir: str | Path,
    grid_size: int = 32,
    write_overlay_png: bool = True,
) -> dict[str, Any]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    luminance = load_luminance(image_path)
    crop_box = auto_crop_non_background(luminance)
    grid = sample_luminance_grid(luminance, crop_box, grid_size, grid_size)
    mask = mass_mask(grid)
    measurement = measure_profile(mask, crop_box=list(crop_box))
    _write_json(out / "profile_measurements.json", measurement)
    overlay = profile_overlay_grid(mask, measurement["boundary_cells"])
    (out / "profile_overlay_grid.txt").write_text(overlay + "\n", encoding="utf-8")
    if write_overlay_png:
        _write_overlay_png(mask, measurement["boundary_cells"], out / "profile_overlay.png")
    return measurement


def classify_shape(measurement: dict[str, Any]) -> str:
    top = measurement["top_width"]
    middle = measurement["middle_width"]
    bottom = measurement["bottom_width"]
    max_width = measurement["max_width_cells"]
    min_width = measurement["min_width_cells"]
    variance = measurement["row_width_variance"]
    if max_width == 0:
        return "unknown"
    if variance <= 1.0 and max_width - min_width <= 2:
        return "rectangle"
    if bottom and top / bottom < 0.85 and middle <= bottom:
        return "taper_column"
    if middle > top and middle > bottom and measurement["curved_profile"]:
        return "circle_or_ellipse"
    return "unknown"


def profile_overlay_grid(mask: list[list[bool]], boundary_cells: list[list[int]]) -> str:
    boundary = {(x, y) for x, y in boundary_cells}
    rows = []
    for y, row in enumerate(mask):
        chars = []
        for x, occupied in enumerate(row):
            if (x, y) in boundary:
                chars.append("B")
            elif occupied:
                chars.append("#")
            else:
                chars.append(".")
        rows.append("".join(chars))
    return "\n".join(rows)


def _curve_rows(widths: list[int], occupied_rows: list[int]) -> tuple[list[int], list[int]]:
    bulges = []
    necks = []
    occupied = set(occupied_rows)
    for row in occupied_rows:
        neighbors = [widths[index] for index in range(max(0, row - 2), min(len(widths), row + 3)) if index != row and index in occupied]
        if len(neighbors) < 2:
            continue
        local = mean(neighbors)
        if widths[row] > local + 1.5:
            bulges.append(row)
        elif widths[row] < local - 1.5:
            necks.append(row)
    return bulges, necks


def _is_smoothly_curved(widths: list[int], occupied_rows: list[int]) -> bool:
    active = [widths[index] for index in occupied_rows]
    if len(active) < 5 or max(active) - min(active) < 3:
        return False
    jumps = [abs(active[index] - active[index - 1]) for index in range(1, len(active))]
    large_jumps = sum(1 for jump in jumps if jump > 4)
    return large_jumps <= max(1, len(jumps) // 5)


def _symmetry_error(contours: dict[str, Any], occupied_rows: list[int], reference_centerline: float | None) -> float | None:
    if reference_centerline is None:
        return None
    offsets = []
    for row in occupied_rows:
        left = contours["left_profile_by_row"][row]
        right = contours["right_profile_by_row"][row]
        if left is None or right is None:
            continue
        offsets.append(abs(((left + right) / 2) - reference_centerline))
    return round(mean(offsets), 4) if offsets else None


def _write_json(path: str | Path, payload: dict[str, Any]) -> None:
    with Path(path).open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def _write_overlay_png(mask: list[list[bool]], boundary_cells: list[list[int]], path: str | Path) -> None:
    scale = 8
    height = len(mask)
    width = len(mask[0]) if height else 0
    image = Image.new("RGBA", (width * scale, height * scale), (255, 255, 255, 255))
    draw = ImageDraw.Draw(image)
    boundary = {(x, y) for x, y in boundary_cells}
    for y, row in enumerate(mask):
        for x, occupied in enumerate(row):
            if not occupied:
                continue
            fill = (40, 40, 40, 255)
            if (x, y) in boundary:
                fill = (210, 40, 35, 255)
            draw.rectangle((x * scale, y * scale, (x + 1) * scale - 1, (y + 1) * scale - 1), fill=fill)
    image.save(path)
