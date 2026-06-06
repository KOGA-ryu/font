from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any
import json

from .compositor import compile_layered_grid
from .image_probe import probe_image
from .motion_select import load_glyph_records, select_motion_glyph


LINEWORK_LAYER_NAME = "linework"


def analyze_linework_image(
    image_path: str | Path,
    pack_dir: str | Path,
    output_dir: str | Path,
    grid_size: int = 32,
    glyphs_path: str | Path | None = None,
    atlas_path: str | Path | None = None,
) -> dict[str, Any]:
    pack = Path(pack_dir)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    glyphs_file = Path(glyphs_path) if glyphs_path is not None else _default_glyphs_path(pack)
    atlas_file = Path(atlas_path) if atlas_path is not None else _default_atlas_path(pack, glyphs_file)

    probe = probe_image(image_path, grid_size, grid_size)
    evidence = analyze_linework_grid(probe["luminance_grid"], probe["edge_map"])
    glyph_records = load_glyph_records(glyphs_file)
    layered, selection_report = evidence_to_layered_grid(evidence, glyph_records)

    layered_path = out / "generated_motion_layered_grid.json"
    evidence_path = out / "linework_evidence.json"
    report_path = out / "motion_selection_report.json"
    _write_json(layered_path, layered)
    _write_json(evidence_path, evidence)
    _write_json(report_path, selection_report)
    manifest = compile_layered_grid(atlas_file, glyphs_file, layered_path, out)
    manifest["linework_motion"] = {
        "evidence_path": str(evidence_path),
        "selection_report_path": str(report_path),
        "motion_profile_counts": selection_report["motion_profile_counts"],
        "selected_token_counts": selection_report["selected_token_counts"],
    }
    _write_json(out / "manifest.json", manifest)
    return {
        "layered_grid_path": str(layered_path),
        "evidence_path": str(evidence_path),
        "selection_report_path": str(report_path),
        "manifest": manifest,
    }


def analyze_linework_grid(
    luminance_grid: list[list[int]],
    edge_grid: list[list[dict[str, Any]]] | None = None,
    ink_threshold: int = 210,
) -> dict[str, Any]:
    height = len(luminance_grid)
    width = len(luminance_grid[0]) if height else 0
    ink = [
        [
            luminance_grid[y][x] < ink_threshold
            or (edge_grid is not None and edge_grid[y][x].get("edge", False) and luminance_grid[y][x] < 238)
            for x in range(width)
        ]
        for y in range(height)
    ]
    cells = []
    for y in range(height):
        for x in range(width):
            if not ink[y][x]:
                continue
            cells.append(_cell_evidence(x, y, luminance_grid, edge_grid, ink))
    return {
        "grid_width": width,
        "grid_height": height,
        "source": "linework_analyzer",
        "linework_cells": cells,
        "motion_profile_counts": dict(Counter(cell["motion_profile"] for cell in cells)),
        "linework_cell_count": len(cells),
    }


def evidence_to_layered_grid(
    evidence: dict[str, Any],
    glyph_records: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    width = int(evidence["grid_width"])
    height = int(evidence["grid_height"])
    grid = [[" " for _ in range(width)] for _ in range(height)]
    metadata = []
    selected_counts: Counter[str] = Counter()
    reasons: Counter[str] = Counter()

    for cell in evidence["linework_cells"]:
        selected = select_motion_glyph(cell, glyph_records)
        token = selected["token"]
        x = int(cell["x"])
        y = int(cell["y"])
        grid[y][x] = token
        selected_counts[token] += 1
        reasons[selected["selection_reason"]] += 1
        metadata.append(
            {
                **cell,
                "token": token,
                "glyph_id": selected["glyph_id"],
                "selection_score": selected["score"],
                "selection_reason": selected["selection_reason"],
            }
        )

    layered = {
        "grid_width": width,
        "grid_height": height,
        "layers": [
            {
                "name": LINEWORK_LAYER_NAME,
                "grid": ["".join(row) for row in grid],
                "cell_metadata": metadata,
            }
        ],
        "metadata": {
            "source": "linework_motion_analyzer",
            "linework_cell_count": len(metadata),
        },
    }
    report = {
        "linework_cell_count": len(metadata),
        "motion_profile_counts": dict(Counter(item["motion_profile"] for item in metadata)),
        "stroke_topology_counts": dict(Counter(item["stroke_topology"] for item in metadata)),
        "selected_token_counts": dict(selected_counts),
        "selection_reason_counts": dict(reasons),
        "cell_metadata": metadata,
    }
    return layered, report


def _cell_evidence(
    x: int,
    y: int,
    grid: list[list[int]],
    edge_grid: list[list[dict[str, Any]]] | None,
    ink: list[list[bool]],
) -> dict[str, Any]:
    direction = _dominant_direction(x, y, edge_grid, ink)
    angle = _angle(direction)
    neighbor_dirs = _neighbor_dirs(x, y, ink)
    topology = _stroke_topology(neighbor_dirs, direction)
    motion_profile = _motion_profile(topology, direction, x, y, ink)
    pressure = _pressure_curve(x, y, grid, ink)
    release = _release_style(motion_profile, topology)
    return {
        "x": x,
        "y": y,
        "layer": LINEWORK_LAYER_NAME,
        "linework_package": _linework_package(motion_profile, topology),
        "stroke_topology": topology,
        "motion_profile": motion_profile,
        "angle_degrees": angle,
        "speed_class": _speed_class(motion_profile, pressure),
        "pressure_curve": pressure,
        "stress_points": _stress_points(motion_profile, topology),
        "release_style": release,
        "dwell": "slight" if pressure == "heavy" else "none",
        "stroke_confidence": _confidence(neighbor_dirs),
        "rhythm_role": "repeat" if motion_profile == "repeated_motion" else "single",
        "continuity": _continuity(motion_profile, topology),
        "neighbor_count": len(neighbor_dirs),
        "confidence": round(_confidence_score(neighbor_dirs, motion_profile), 3),
    }


def _dominant_direction(
    x: int,
    y: int,
    edge_grid: list[list[dict[str, Any]]] | None,
    ink: list[list[bool]],
) -> str:
    if edge_grid is not None:
        direction = edge_grid[y][x].get("direction")
        if direction in {"horizontal", "vertical", "diagonal_rise", "diagonal_fall"}:
            return direction
    counts = Counter(_direction_from_delta(dx, dy) for dx, dy in _neighbor_dirs(x, y, ink))
    return counts.most_common(1)[0][0] if counts else "horizontal"


def _neighbor_dirs(x: int, y: int, ink: list[list[bool]]) -> list[tuple[int, int]]:
    height = len(ink)
    width = len(ink[0]) if height else 0
    result = []
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx = x + dx
            ny = y + dy
            if 0 <= nx < width and 0 <= ny < height and ink[ny][nx]:
                result.append((dx, dy))
    return result


def _stroke_topology(neighbor_dirs: list[tuple[int, int]], direction: str) -> str:
    count = len(neighbor_dirs)
    if count <= 1:
        return "terminal_segment"
    if count >= 4:
        return "repeated_strokes"
    if count == 3:
        return "direction_change"
    a, b = neighbor_dirs[:2]
    if a[0] == -b[0] and a[1] == -b[1]:
        return "pass_through_segment"
    return "direction_change"


def _motion_profile(topology: str, direction: str, x: int, y: int, ink: list[list[bool]]) -> str:
    if topology == "repeated_strokes":
        return "repeated_motion"
    if topology == "terminal_segment":
        return "press_and_stop"
    if _has_implied_gap(x, y, direction, ink):
        return "interrupted_pull"
    if topology == "direction_change":
        return "direction_change"
    if direction.startswith("diagonal"):
        return "angled_pull"
    return "steady_pull"


def _has_implied_gap(x: int, y: int, direction: str, ink: list[list[bool]]) -> bool:
    vectors = {
        "horizontal": ((-1, 0), (1, 0)),
        "vertical": ((0, -1), (0, 1)),
        "diagonal_rise": ((-1, 1), (1, -1)),
        "diagonal_fall": ((-1, -1), (1, 1)),
    }[direction]
    height = len(ink)
    width = len(ink[0]) if height else 0
    for dx, dy in vectors:
        near = (x + dx, y + dy)
        far = (x + dx * 2, y + dy * 2)
        if 0 <= far[0] < width and 0 <= far[1] < height and 0 <= near[0] < width and 0 <= near[1] < height:
            if not ink[near[1]][near[0]] and ink[far[1]][far[0]]:
                return True
    return False


def _pressure_curve(x: int, y: int, grid: list[list[int]], ink: list[list[bool]]) -> str:
    dark = grid[y][x]
    local = sum(1 for dx, dy in _neighbor_dirs(x, y, ink) if True)
    if dark < 80 or local >= 5:
        return "heavy"
    if dark < 145 or local >= 3:
        return "medium"
    return "thin"


def _linework_package(motion_profile: str, topology: str) -> str:
    if motion_profile == "repeated_motion":
        return "linework.pattern"
    if motion_profile == "interrupted_pull":
        return "linework.break"
    if topology == "terminal_segment":
        return "linework.terminal"
    if topology == "direction_change":
        return "linework.join"
    return "linework.stroke"


def _release_style(motion_profile: str, topology: str) -> str:
    if motion_profile == "interrupted_pull":
        return "dry_break"
    if topology == "terminal_segment":
        return "blunt_stop"
    return "clean_exit"


def _speed_class(motion_profile: str, pressure: str) -> str:
    if motion_profile in {"repeated_motion", "interrupted_pull"}:
        return "fast"
    if pressure == "heavy":
        return "slow"
    return "medium"


def _stress_points(motion_profile: str, topology: str) -> list[str]:
    if topology == "direction_change":
        return ["corner"]
    if motion_profile == "repeated_motion":
        return ["repeat_accent"]
    return []


def _confidence(neighbor_dirs: list[tuple[int, int]]) -> str:
    return "decisive" if neighbor_dirs else "searching"


def _confidence_score(neighbor_dirs: list[tuple[int, int]], motion_profile: str) -> float:
    base = min(0.95, 0.45 + len(neighbor_dirs) * 0.1)
    if motion_profile in {"steady_pull", "angled_pull", "repeated_motion"}:
        base += 0.05
    return min(base, 0.98)


def _continuity(motion_profile: str, topology: str) -> str:
    if motion_profile == "interrupted_pull":
        return "implied_through_gap"
    if topology == "terminal_segment":
        return "terminates"
    if topology == "direction_change":
        return "joined"
    return "continuous"


def _direction_from_delta(dx: int, dy: int) -> str:
    if dy == 0:
        return "horizontal"
    if dx == 0:
        return "vertical"
    if dx * dy < 0:
        return "diagonal_rise"
    return "diagonal_fall"


def _angle(direction: str) -> float:
    return {
        "horizontal": 0.0,
        "vertical": 90.0,
        "diagonal_rise": 45.0,
        "diagonal_fall": 135.0,
    }[direction]


def _default_glyphs_path(pack: Path) -> Path:
    promoted = pack / "glyphs.promoted.json"
    return promoted if promoted.exists() else pack / "glyphs.json"


def _default_atlas_path(pack: Path, glyphs_path: Path) -> Path:
    promoted = pack / "atlas.promoted.png"
    if glyphs_path.name == "glyphs.promoted.json" and promoted.exists():
        return promoted
    return pack / "atlas.png"


def _write_json(path: str | Path, payload: dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
