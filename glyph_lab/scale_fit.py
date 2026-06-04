from __future__ import annotations

from typing import Any


def fit_to_grid(
    measurements: dict[str, Any],
    target_width: int,
    target_height: int,
    padding_cells: int = 0,
) -> dict[str, Any]:
    if target_width <= 0 or target_height <= 0:
        raise ValueError("target_width and target_height must be positive")
    if padding_cells < 0:
        raise ValueError("padding_cells must be non-negative")
    occupied_width, occupied_height = _occupied_size(measurements)
    available_width = target_width - padding_cells * 2
    available_height = target_height - padding_cells * 2
    if available_width <= 0 or available_height <= 0:
        raise ValueError("padding_cells leaves no drawable grid area")

    warning = None
    if occupied_width <= 0 or occupied_height <= 0:
        scale_factor = 0.0
        warning = "object_too_small"
    else:
        scale_factor = min(available_width / occupied_width, available_height / occupied_height)
        if occupied_width > available_width or occupied_height > available_height:
            warning = "object_too_large"
        elif scale_factor >= 2.0:
            warning = "object_too_small"

    fitted_width = round(occupied_width * scale_factor) if occupied_width > 0 else 0
    fitted_height = round(occupied_height * scale_factor) if occupied_height > 0 else 0
    leftover_x = max(0, target_width - fitted_width)
    leftover_y = max(0, target_height - fitted_height)
    padding_left = leftover_x // 2
    padding_right = leftover_x - padding_left
    padding_top = leftover_y // 2
    padding_bottom = leftover_y - padding_top

    return {
        "target_width": target_width,
        "target_height": target_height,
        "occupied_width": occupied_width,
        "occupied_height": occupied_height,
        "scale_factor": round(scale_factor, 4),
        "padding_left": padding_left,
        "padding_right": padding_right,
        "padding_top": padding_top,
        "padding_bottom": padding_bottom,
        "warning": warning,
    }


def _occupied_size(measurements: dict[str, Any]) -> tuple[int, int]:
    bbox = measurements.get("occupied_bbox_cells")
    if bbox:
        return int(bbox[2] - bbox[0] + 1), int(bbox[3] - bbox[1] + 1)
    width = measurements.get("max_width_cells") or measurements.get("occupied_width") or 0
    height = measurements.get("total_height_cells") or measurements.get("occupied_height") or 0
    return int(width), int(height)
