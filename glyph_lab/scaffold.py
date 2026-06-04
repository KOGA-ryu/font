from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from PIL import Image, ImageDraw

from .anchors import detect_anchor_points
from .bands import detect_horizontal_bands, measure_bands
from .contours import extract_contours
from .grooves import detect_vertical_grooves, measure_grooves
from .image_probe import auto_crop_non_background, edge_map, load_luminance, mass_mask, sample_luminance_grid
from .profiles import measure_profile
from .scale_fit import fit_to_grid


def detect_support_lines(
    mask: list[list[bool]],
    profile: dict[str, Any],
    rhythm: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    rhythm = rhythm or {}
    bbox = profile.get("occupied_bbox_cells")
    if not bbox:
        return []
    x1, y1, x2, y2 = [int(value) for value in bbox]
    center_x = round(float(profile.get("centerline_x_estimate", (x1 + x2) / 2)))
    center_y = round((y1 + y2) / 2)
    height = y2 - y1 + 1
    width = x2 - x1 + 1
    grid_width = len(mask[0]) if mask else 0
    grid_center = (grid_width - 1) / 2 if grid_width else center_x
    feature_count = len(rhythm.get("bands", [])) + len(rhythm.get("grooves", []))

    candidates = [
        _line(
            "support.vertical_centerline",
            "vertical",
            center_x,
            y1,
            center_x,
            y2,
            90.0,
            _score(height, height, 1.0 - min(1.0, abs(center_x - grid_center) / max(1, grid_width)), feature_count),
            [
                "spans occupied silhouette height",
                "agrees with profile centerline",
                "supports center-out construction",
            ],
        ),
        _line(
            "support.bottom_baseline",
            "horizontal",
            x1,
            y2,
            x2,
            y2,
            0.0,
            _score(width, height, 0.65, len(rhythm.get("bands", []))),
            ["bottom occupied row provides a baseline candidate"],
        ),
        _line(
            "support.middle_horizontal",
            "horizontal",
            x1,
            center_y,
            x2,
            center_y,
            0.0,
            _score(width, height, 0.45, len(rhythm.get("bands", []))),
            ["midline can carry band and proportion checks"],
        ),
    ]
    candidates.extend(_dominant_boundary_runs(mask, profile))
    return sorted(candidates, key=lambda item: item["score"], reverse=True)


def build_scaffold(
    mask: list[list[bool]],
    profile: dict[str, Any],
    rhythm: dict[str, Any] | None = None,
    target_width: int | None = None,
    target_height: int | None = None,
    padding_cells: int = 2,
) -> dict[str, Any]:
    rhythm = rhythm or {}
    candidates = detect_support_lines(mask, profile, rhythm)
    primary = candidates[0] if candidates else None
    anchors = detect_anchor_points(profile, rhythm, profile.get("boundary_cells", []))
    attached = detect_attached_lines(primary, anchors, rhythm)
    angle_measurements = measure_attached_angles(primary, attached)
    grid_size = profile.get("grid_size") or [len(mask[0]) if mask else 0, len(mask)]
    scale = fit_to_grid(
        profile,
        target_width or int(grid_size[0]),
        target_height or int(grid_size[1]),
        padding_cells,
    )
    return {
        "primary_support_line": _strip_score(primary),
        "support_line_candidates": [_strip_score(candidate) for candidate in candidates],
        "anchor_points": anchors,
        "attached_lines": attached,
        "angle_measurements": angle_measurements,
        "scale_fit": scale,
        "confidence": primary["confidence"] if primary else 0.0,
    }


def detect_attached_lines(
    primary_support_line: dict[str, Any] | None,
    anchors: list[dict[str, Any]],
    rhythm: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if not primary_support_line:
        return []
    rhythm = rhythm or {}
    support_id = primary_support_line["id"]
    by_y_source = {(anchor["y"], anchor["source"]): anchor["id"] for anchor in anchors}
    lines = []
    for index, band in enumerate(rhythm.get("bands", [])):
        y = int(band["y_cell"])
        anchor_id = by_y_source.get((y, "band_row"), f"anchor.band_{index:02d}")
        lines.append(
            {
                "id": f"line.band_{index:02d}",
                "parent_support": support_id,
                "anchor_id": anchor_id,
                "kind": "horizontal",
                "angle_degrees": 0.0,
                "length": int(band["x_end"]) - int(band["x_start"]) + 1,
                "confidence": round(float(band.get("confidence", 0.7)), 4),
            }
        )
    for index, groove in enumerate(rhythm.get("grooves", [])):
        lines.append(
            {
                "id": f"line.groove_{index:02d}",
                "parent_support": support_id,
                "anchor_id": f"anchor.groove_{index:02d}_start",
                "kind": "vertical_parallel",
                "angle_degrees": 90.0,
                "length": int(groove["length"]),
                "confidence": round(float(groove.get("confidence", 0.65)), 4),
            }
        )
    return lines


def measure_attached_angles(
    primary_support_line: dict[str, Any] | None,
    attached_lines: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not primary_support_line:
        return []
    support_angle = float(primary_support_line["angle_degrees"])
    measurements = []
    for line in attached_lines:
        delta = abs(float(line["angle_degrees"]) - support_angle) % 180
        if delta > 90:
            delta = 180 - delta
        measurements.append(
            {
                "line_id": line["id"],
                "support_line_id": primary_support_line["id"],
                "angle_degrees": round(float(line["angle_degrees"]), 4),
                "relative_to_support_degrees": round(delta, 4),
                "confidence": min(primary_support_line["confidence"], line["confidence"]),
            }
        )
    return measurements


def measure_scaffold_image(
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
    profile = measure_profile(mask, crop_box=list(crop_box))
    grooves = detect_vertical_grooves(grid, mask, edges)
    bands = detect_horizontal_bands(grid, mask, edges)
    rhythm = {
        "grid_size": [grid_size, grid_size],
        **measure_grooves(grooves),
        **measure_bands(bands),
    }
    scaffold = build_scaffold(
        mask,
        profile,
        rhythm,
        target_width=grid_size,
        target_height=grid_size,
        padding_cells=2,
    )
    result = {
        "crop_box": list(crop_box),
        "grid_size": [grid_size, grid_size],
        "support_scaffold": scaffold,
        "primary_support_line": scaffold["primary_support_line"],
        "anchor_points": scaffold["anchor_points"],
        "attached_lines": scaffold["attached_lines"],
        "angle_measurements": scaffold["angle_measurements"],
        "scale_fit": scaffold["scale_fit"],
    }
    overlay = scaffold_overlay_grid(mask, scaffold)
    _write_json(out / "scaffold_measurements.json", result)
    (out / "scaffold_overlay_grid.txt").write_text(overlay + "\n", encoding="utf-8")
    if write_overlay_png:
        _write_overlay_png(overlay, out / "scaffold_overlay.png")
    return result


def scaffold_overlay_grid(mask: list[list[bool]], scaffold: dict[str, Any]) -> str:
    height = len(mask)
    width = len(mask[0]) if height else 0
    rows = [["." if mask[y][x] else " " for x in range(width)] for y in range(height)]
    primary = scaffold.get("primary_support_line")
    if primary:
        _draw_line(rows, primary, primary_char="|" if primary["kind"] == "vertical" else "-")
    for line in scaffold.get("attached_lines", []):
        char = "-" if line["kind"] == "horizontal" else "?"
        _draw_attached_line(rows, line, scaffold.get("anchor_points", []), char)
    for anchor in scaffold.get("anchor_points", []):
        x = int(anchor["x"])
        y = int(anchor["y"])
        if 0 <= y < height and 0 <= x < width:
            rows[y][x] = "+"
    return "\n".join("".join(row) for row in rows)


def _line(
    line_id: str,
    kind: str,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    angle: float,
    score: float,
    reasons: list[str],
) -> dict[str, Any]:
    length = abs(y2 - y1) + 1 if kind == "vertical" else abs(x2 - x1) + 1
    confidence = max(0.0, min(1.0, score))
    return {
        "id": line_id,
        "kind": kind,
        "x1": int(x1),
        "y1": int(y1),
        "x2": int(x2),
        "y2": int(y2),
        "length": float(length),
        "angle_degrees": float(angle),
        "confidence": round(confidence, 4),
        "reasons": reasons,
        "score": score,
    }


def _score(length: int, reference_length: int, centeredness: float, feature_count: int) -> float:
    length_score = min(1.0, length / max(1, reference_length))
    feature_score = min(0.25, feature_count * 0.04)
    return round(min(1.0, length_score * 0.62 + centeredness * 0.24 + feature_score), 4)


def _dominant_boundary_runs(mask: list[list[bool]], profile: dict[str, Any]) -> list[dict[str, Any]]:
    contours = extract_contours(mask)
    boundary = {(x, y) for x, y in contours["boundary_cells"]}
    if not boundary:
        return []
    bbox = profile.get("occupied_bbox_cells") or contours["occupied_bbox_cells"]
    if not bbox:
        return []
    height = bbox[3] - bbox[1] + 1
    width = bbox[2] - bbox[0] + 1
    vertical = _longest_vertical_run(boundary)
    horizontal = _longest_horizontal_run(boundary)
    candidates = []
    if vertical:
        x, y1, y2 = vertical
        candidates.append(
            _line(
                f"support.boundary_vertical_x{x}",
                "vertical",
                x,
                y1,
                x,
                y2,
                90.0,
                _score(y2 - y1 + 1, height, 0.55, 0),
                ["long straight vertical boundary run"],
            )
        )
    if horizontal:
        y, x1, x2 = horizontal
        candidates.append(
            _line(
                f"support.boundary_horizontal_y{y}",
                "horizontal",
                x1,
                y,
                x2,
                y,
                0.0,
                _score(x2 - x1 + 1, width, 0.5, 0),
                ["long straight horizontal boundary run"],
            )
        )
    return candidates


def _longest_vertical_run(boundary: set[tuple[int, int]]) -> tuple[int, int, int] | None:
    best = None
    for x in sorted({point[0] for point in boundary}):
        ys = sorted(y for bx, y in boundary if bx == x)
        for run in _runs(ys):
            candidate = (x, run[0], run[-1])
            if best is None or (candidate[2] - candidate[1]) > (best[2] - best[1]):
                best = candidate
    return best


def _longest_horizontal_run(boundary: set[tuple[int, int]]) -> tuple[int, int, int] | None:
    best = None
    for y in sorted({point[1] for point in boundary}):
        xs = sorted(x for x, by in boundary if by == y)
        for run in _runs(xs):
            candidate = (y, run[0], run[-1])
            if best is None or (candidate[2] - candidate[1]) > (best[2] - best[1]):
                best = candidate
    return best


def _runs(values: list[int]) -> list[list[int]]:
    if not values:
        return []
    runs = [[values[0]]]
    for value in values[1:]:
        if value == runs[-1][-1] + 1:
            runs[-1].append(value)
        else:
            runs.append([value])
    return runs


def _strip_score(line: dict[str, Any] | None) -> dict[str, Any] | None:
    if line is None:
        return None
    return {key: value for key, value in line.items() if key != "score"}


def _draw_line(rows: list[list[str]], line: dict[str, Any], primary_char: str) -> None:
    height = len(rows)
    width = len(rows[0]) if height else 0
    if line["kind"] == "vertical":
        x = int(line["x1"])
        for y in range(int(line["y1"]), int(line["y2"]) + 1):
            if 0 <= y < height and 0 <= x < width:
                rows[y][x] = primary_char
    else:
        y = int(line["y1"])
        for x in range(int(line["x1"]), int(line["x2"]) + 1):
            if 0 <= y < height and 0 <= x < width:
                rows[y][x] = primary_char


def _draw_attached_line(rows: list[list[str]], line: dict[str, Any], anchors: list[dict[str, Any]], char: str) -> None:
    if line["kind"] != "horizontal":
        return
    anchor = next((item for item in anchors if item["id"] == line["anchor_id"]), None)
    if not anchor:
        return
    height = len(rows)
    width = len(rows[0]) if height else 0
    y = int(anchor["y"])
    half = max(1, round(line["length"] / 2))
    center_x = int(anchor["x"])
    for x in range(center_x - half, center_x + half + 1):
        if 0 <= y < height and 0 <= x < width:
            rows[y][x] = char


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
        ".": (222, 222, 222, 255),
        "|": (30, 70, 220, 255),
        "-": (220, 95, 35, 255),
        "+": (135, 35, 170, 255),
        "?": (40, 40, 40, 255),
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
