from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image


WHITE_BACKGROUND_THRESHOLD = 245


def load_luminance(path: str | Path) -> Image.Image:
    return Image.open(path).convert("L")


def auto_crop_non_background(
    image: Image.Image,
    threshold: int = WHITE_BACKGROUND_THRESHOLD,
) -> tuple[int, int, int, int]:
    luminance = image.convert("L")
    pixels = luminance.load()
    xs: list[int] = []
    ys: list[int] = []
    for y in range(luminance.height):
        for x in range(luminance.width):
            if pixels[x, y] < threshold:
                xs.append(x)
                ys.append(y)
    if not xs:
        return (0, 0, luminance.width, luminance.height)
    return (min(xs), min(ys), max(xs) + 1, max(ys) + 1)


def sample_luminance_grid(
    image: Image.Image,
    crop_box: tuple[int, int, int, int],
    grid_width: int,
    grid_height: int,
    padding: int = 2,
) -> list[list[int]]:
    crop = _padded_crop(image.convert("L"), crop_box, padding)
    resized = crop.resize((grid_width, grid_height), Image.Resampling.BOX)
    pixels = resized.load()
    return [[int(pixels[x, y]) for x in range(grid_width)] for y in range(grid_height)]


def mass_mask(grid: list[list[int]], threshold: int = 235) -> list[list[bool]]:
    return [[value < threshold for value in row] for row in grid]


def value_band_map(grid: list[list[int]], mask: list[list[bool]]) -> list[list[str]]:
    bands: list[list[str]] = []
    for y, row in enumerate(grid):
        band_row = []
        for x, value in enumerate(row):
            if not mask[y][x]:
                band_row.append("background")
            elif value < 85:
                band_row.append("dark")
            elif value > 175:
                band_row.append("light")
            else:
                band_row.append("mid")
        bands.append(band_row)
    return bands


def edge_map(grid: list[list[int]], threshold: int = 45) -> list[list[dict[str, Any]]]:
    height = len(grid)
    width = len(grid[0]) if height else 0
    result: list[list[dict[str, Any]]] = []
    for y in range(height):
        row = []
        for x in range(width):
            left = grid[y][max(0, x - 1)]
            right = grid[y][min(width - 1, x + 1)]
            top = grid[max(0, y - 1)][x]
            bottom = grid[min(height - 1, y + 1)][x]
            gx = int(right) - int(left)
            gy = int(bottom) - int(top)
            magnitude = abs(gx) + abs(gy)
            row.append(
                {
                    "edge": magnitude >= threshold,
                    "magnitude": magnitude,
                    "direction": _direction(gx, gy),
                }
            )
        result.append(row)
    return result


def probe_image(
    image_path: str | Path,
    grid_width: int = 32,
    grid_height: int = 32,
) -> dict[str, Any]:
    luminance = load_luminance(image_path)
    crop_box = auto_crop_non_background(luminance)
    grid = sample_luminance_grid(luminance, crop_box, grid_width, grid_height)
    mask = mass_mask(grid)
    bands = value_band_map(grid, mask)
    edges = edge_map(grid)
    occupied = [(x, y) for y, row in enumerate(mask) for x, value in enumerate(row) if value]
    edge_count = sum(1 for row in edges for cell in row if cell["edge"])
    band_counts: dict[str, int] = {"background": 0, "dark": 0, "mid": 0, "light": 0}
    for row in bands:
        for band in row:
            band_counts[band] += 1
    return {
        "original_image_size": [luminance.width, luminance.height],
        "crop_box": list(crop_box),
        "grid_width": grid_width,
        "grid_height": grid_height,
        "luminance_grid": grid,
        "mass_mask": mask,
        "value_band_map": bands,
        "edge_map": edges,
        "occupied_cell_count": len(occupied),
        "occupied_bbox_cells": _bbox(occupied),
        "centerline_x_estimate": _centerline_x(occupied),
        "value_band_counts": band_counts,
        "edge_cell_count": edge_count,
    }


def measurement_summary(probe: dict[str, Any]) -> dict[str, Any]:
    return {
        "original_image_size": probe["original_image_size"],
        "crop_box": probe["crop_box"],
        "grid_width": probe["grid_width"],
        "grid_height": probe["grid_height"],
        "occupied_cell_count": probe["occupied_cell_count"],
        "occupied_bbox_cells": probe["occupied_bbox_cells"],
        "centerline_x_estimate": probe["centerline_x_estimate"],
        "value_band_counts": probe["value_band_counts"],
        "edge_cell_count": probe["edge_cell_count"],
    }


def _padded_crop(image: Image.Image, crop_box: tuple[int, int, int, int], padding: int) -> Image.Image:
    left, top, right, bottom = crop_box
    box = (
        max(0, left - padding),
        max(0, top - padding),
        min(image.width, right + padding),
        min(image.height, bottom + padding),
    )
    return image.crop(box)


def _direction(gx: int, gy: int) -> str:
    ax = abs(gx)
    ay = abs(gy)
    if ax > ay * 2:
        return "vertical"
    if ay > ax * 2:
        return "horizontal"
    if gx * gy >= 0:
        return "diagonal_fall"
    return "diagonal_rise"


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
