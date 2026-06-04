from __future__ import annotations

from typing import Any


def extract_contours(mask: list[list[bool]]) -> dict[str, Any]:
    height = len(mask)
    width = len(mask[0]) if height else 0
    boundary = []
    occupied = []
    left_profile: list[int | None] = []
    right_profile: list[int | None] = []
    width_profile: list[int] = []

    for y, row in enumerate(mask):
        xs = [x for x, value in enumerate(row) if value]
        if xs:
            left = min(xs)
            right = max(xs)
            left_profile.append(left)
            right_profile.append(right)
            width_profile.append(right - left + 1)
            occupied.extend((x, y) for x in xs)
        else:
            left_profile.append(None)
            right_profile.append(None)
            width_profile.append(0)

        for x in xs:
            if _is_boundary(mask, x, y, width, height):
                boundary.append([x, y])

    return {
        "boundary_cells": boundary,
        "contour_cells": boundary,
        "occupied_bbox_cells": _bbox(occupied),
        "centerline_x_estimate": _centerline_x(occupied),
        "left_profile_by_row": left_profile,
        "right_profile_by_row": right_profile,
        "width_profile_by_row": width_profile,
    }


def _is_boundary(mask: list[list[bool]], x: int, y: int, width: int, height: int) -> bool:
    for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
        if nx < 0 or ny < 0 or nx >= width or ny >= height:
            return True
        if not mask[ny][nx]:
            return True
    return False


def _bbox(points: list[tuple[int, int]]) -> list[int] | None:
    if not points:
        return None
    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    return [min(xs), min(ys), max(xs), max(ys)]


def _centerline_x(points: list[tuple[int, int]]) -> float | None:
    if not points:
        return None
    xs = [x for x, _ in points]
    return (min(xs) + max(xs)) / 2
