from __future__ import annotations

from pathlib import Path
from statistics import mean
from typing import Any
import json

from PIL import Image, ImageDraw

from .bands import detect_horizontal_bands, measure_bands
from .image_probe import auto_crop_non_background, edge_map, load_luminance, mass_mask, sample_luminance_grid


def detect_vertical_grooves(
    luminance_grid: list[list[int]],
    mask: list[list[bool]],
    edge_grid: list[list[dict[str, Any]]] | None = None,
) -> list[dict[str, Any]]:
    height = len(luminance_grid)
    width = len(luminance_grid[0]) if height else 0
    if not width:
        return []
    column_scores = [_column_activity(luminance_grid, mask, edge_grid, x) for x in range(width)]
    active_scores = [score for score in column_scores if score > 0]
    if not active_scores:
        return []
    threshold = mean(active_scores) + 0.08
    candidates = [
        x
        for x, score in enumerate(column_scores)
        if score >= threshold and score >= column_scores[max(0, x - 1)] and score >= column_scores[min(width - 1, x + 1)]
    ]
    runs = _merge_positions(candidates, max_gap=1)
    grooves = []
    for run in runs:
        x_cell = round(mean(run))
        y_cells = [y for y in range(height) if mask[y][x_cell]]
        if not y_cells:
            continue
        darkness_values = [
            (255 - luminance_grid[y][x]) / 255
            for x in run
            for y in range(height)
            if mask[y][x]
        ]
        y_start = min(y_cells)
        y_end = max(y_cells)
        length = y_end - y_start + 1
        confidence = min(1.0, column_scores[x_cell] * (length / max(1, height)) * 1.4)
        if length < max(4, height // 4) or confidence < 0.18:
            continue
        grooves.append(
            {
                "x_cell": x_cell,
                "y_start": y_start,
                "y_end": y_end,
                "length": length,
                "average_darkness": round(mean(darkness_values), 4) if darkness_values else 0,
                "confidence": round(confidence, 4),
            }
        )
    return grooves


def measure_grooves(grooves: list[dict[str, Any]]) -> dict[str, Any]:
    xs = [groove["x_cell"] for groove in grooves]
    spacings = [xs[index] - xs[index - 1] for index in range(1, len(xs))]
    lengths = [groove["length"] for groove in grooves]
    bbox = None
    if grooves:
        bbox = [min(xs), min(g["y_start"] for g in grooves), max(xs), max(g["y_end"] for g in grooves)]
    spacing_variance = _variance(spacings)
    average_spacing = round(mean(spacings), 4) if spacings else None
    rhythm_confidence = _rhythm_confidence(grooves, spacing_variance)
    return {
        "groove_count": len(grooves),
        "grooves": grooves,
        "average_groove_spacing": average_spacing,
        "groove_spacing_variance": spacing_variance,
        "average_length": round(mean(lengths), 4) if lengths else 0,
        "groove_region_bbox": bbox,
        "rhythm_confidence": rhythm_confidence,
        "likely_repeated_grooves": len(grooves) >= 4 and rhythm_confidence >= 0.45,
    }


def measure_rhythm_image(
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
    edges = edge_map(grid)
    grooves = detect_vertical_grooves(grid, mask, edges)
    bands = detect_horizontal_bands(grid, mask, edges)
    groove_measurements = measure_grooves(grooves)
    band_measurements = measure_bands(bands)
    overlay = rhythm_overlay_grid(mask, grooves, bands)
    measurements = {
        "crop_box": list(crop_box),
        "grid_size": [grid_size, grid_size],
        **groove_measurements,
        **band_measurements,
    }
    _write_json(out / "rhythm_measurements.json", measurements)
    (out / "rhythm_overlay_grid.txt").write_text(overlay + "\n", encoding="utf-8")
    if write_overlay_png:
        _write_overlay_png(overlay, out / "rhythm_overlay.png")
    return measurements


def rhythm_overlay_grid(
    mask: list[list[bool]],
    grooves: list[dict[str, Any]],
    bands: list[dict[str, Any]],
) -> str:
    height = len(mask)
    width = len(mask[0]) if height else 0
    rows = [["." if mask[y][x] else " " for x in range(width)] for y in range(height)]
    for groove in grooves:
        x = groove["x_cell"]
        for y in range(groove["y_start"], groove["y_end"] + 1):
            if 0 <= y < height and 0 <= x < width:
                rows[y][x] = "|"
    for band in bands:
        for y in range(band["y_cell"], band["y_cell"] + band["thickness"]):
            for x in range(band["x_start"], band["x_end"] + 1):
                if 0 <= y < height and 0 <= x < width:
                    rows[y][x] = "+" if rows[y][x] == "|" else "="
    return "\n".join("".join(row) for row in rows)


def _column_activity(
    luminance_grid: list[list[int]],
    mask: list[list[bool]],
    edge_grid: list[list[dict[str, Any]]] | None,
    x: int,
) -> float:
    values = []
    for y, row in enumerate(luminance_grid):
        if not mask[y][x]:
            continue
        darkness = (255 - row[x]) / 255
        edge_bonus = 0.0
        if edge_grid is not None and edge_grid[y][x]["edge"]:
            edge_bonus = min(0.25, edge_grid[y][x]["magnitude"] / 1020)
        values.append(darkness + edge_bonus)
    return mean(values) if values else 0.0


def _merge_positions(positions: list[int], max_gap: int) -> list[list[int]]:
    if not positions:
        return []
    positions = sorted(positions)
    runs = [[positions[0]]]
    for value in positions[1:]:
        if value - runs[-1][-1] <= max_gap:
            runs[-1].append(value)
        else:
            runs.append([value])
    return runs


def _rhythm_confidence(grooves: list[dict[str, Any]], spacing_variance: float | None) -> float:
    if len(grooves) < 2:
        return 0.0
    avg_conf = mean(groove["confidence"] for groove in grooves)
    variance_penalty = min(0.5, (spacing_variance or 0) / 8)
    count_bonus = min(0.25, len(grooves) / 32)
    return round(max(0.0, min(1.0, avg_conf + count_bonus - variance_penalty)), 4)


def _variance(values: list[int]) -> float | None:
    if not values:
        return None
    avg = mean(values)
    return round(mean((value - avg) ** 2 for value in values), 4)


def _write_json(path: str | Path, payload: dict[str, Any]) -> None:
    with Path(path).open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def _write_overlay_png(overlay: str, path: str | Path) -> None:
    rows = overlay.splitlines()
    height = len(rows)
    width = len(rows[0]) if height else 0
    scale = 8
    colors = {
        " ": (255, 255, 255, 255),
        ".": (218, 218, 218, 255),
        "|": (35, 60, 210, 255),
        "=": (210, 80, 35, 255),
        "+": (130, 40, 160, 255),
    }
    image = Image.new("RGBA", (width * scale, height * scale), (255, 255, 255, 255))
    draw = ImageDraw.Draw(image)
    for y, row in enumerate(rows):
        for x, char in enumerate(row):
            draw.rectangle(
                (x * scale, y * scale, (x + 1) * scale - 1, (y + 1) * scale - 1),
                fill=colors.get(char, (0, 0, 0, 255)),
            )
    image.save(path)
