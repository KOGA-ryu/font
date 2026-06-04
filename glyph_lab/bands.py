from __future__ import annotations

from statistics import mean
from typing import Any


def detect_horizontal_bands(
    luminance_grid: list[list[int]],
    mask: list[list[bool]],
    edge_grid: list[list[dict[str, Any]]] | None = None,
) -> list[dict[str, Any]]:
    height = len(luminance_grid)
    width = len(luminance_grid[0]) if height else 0
    if not height:
        return []
    row_scores = [_row_activity(luminance_grid, mask, edge_grid, y) for y in range(height)]
    active_scores = [score for score in row_scores if score > 0]
    if not active_scores:
        return []
    threshold = mean(active_scores) + 0.08
    candidates = [y for y, score in enumerate(row_scores) if score >= threshold]
    runs = _merge_positions(candidates, max_gap=1)
    bands = []
    for run in runs:
        y_cell = run[0]
        x_cells = [x for y in run for x in range(width) if mask[y][x]]
        if not x_cells:
            continue
        darkness_values = [
            (255 - luminance_grid[y][x]) / 255
            for y in run
            for x in range(width)
            if mask[y][x]
        ]
        confidence = min(1.0, mean(row_scores[y] for y in run) * (len(set(x_cells)) / max(1, width)) * 1.5)
        if confidence < 0.18:
            continue
        bands.append(
            {
                "y_cell": y_cell,
                "x_start": min(x_cells),
                "x_end": max(x_cells),
                "thickness": len(run),
                "average_darkness": round(mean(darkness_values), 4) if darkness_values else 0,
                "confidence": round(confidence, 4),
            }
        )
    return bands


def measure_bands(bands: list[dict[str, Any]]) -> dict[str, Any]:
    ys = [band["y_cell"] for band in bands]
    spacings = [ys[index] - ys[index - 1] for index in range(1, len(ys))]
    spacing_variance = _variance(spacings)
    likely = len(bands) >= 3 and (spacing_variance is None or spacing_variance <= 12)
    return {
        "band_count": len(bands),
        "bands": bands,
        "average_band_spacing": round(mean(spacings), 4) if spacings else None,
        "band_spacing_variance": spacing_variance,
        "major_band_rows": ys,
        "likely_moulding_stack": likely,
    }


def _row_activity(
    luminance_grid: list[list[int]],
    mask: list[list[bool]],
    edge_grid: list[list[dict[str, Any]]] | None,
    y: int,
) -> float:
    values = []
    for x, value in enumerate(luminance_grid[y]):
        if not mask[y][x]:
            continue
        darkness = (255 - value) / 255
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


def _variance(values: list[int]) -> float | None:
    if not values:
        return None
    avg = mean(values)
    return round(mean((value - avg) ** 2 for value in values), 4)
