from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any
import json

from PIL import Image, ImageDraw, ImageFont

from .image_probe import auto_crop_non_background, probe_image
from .linework_analyzer import analyze_linework_image


PANEL_SIZE = 160
PANEL_PADDING = 12
TEXT_HEIGHT = 62


def write_layer_breakdown(
    image_path: str | Path,
    pack_dir: str | Path,
    output_dir: str | Path,
    motion_out_dir: str | Path | None = None,
    grid_size: int = 32,
) -> dict[str, Any]:
    image = Path(image_path)
    pack = Path(pack_dir)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    motion_out = Path(motion_out_dir) if motion_out_dir is not None else out / "motion"
    if not (motion_out / "motion_selection_report.json").exists():
        analyze_linework_image(image, pack, motion_out, grid_size=grid_size)

    probe = probe_image(image, grid_size, grid_size)
    layered = _load_json(motion_out / "generated_motion_layered_grid.json")
    report = _load_json(motion_out / "motion_selection_report.json")
    manifest = _load_json(motion_out / "manifest.json")

    panels = _build_panels(image, probe, layered, motion_out)
    summary = _summary(image, motion_out, probe, report, manifest, panels)
    sheet = _render_sheet(panels, summary)

    image_out = out / "layer_breakdown.png"
    json_out = out / "layer_breakdown.json"
    sheet.save(image_out)
    summary["output_paths"] = {
        "layer_breakdown_png": str(image_out),
        "layer_breakdown_json": str(json_out),
    }
    _write_json(json_out, summary)
    return summary


def _build_panels(
    image_path: Path,
    probe: dict[str, Any],
    layered: dict[str, Any],
    motion_out: Path,
) -> list[dict[str, Any]]:
    original = Image.open(image_path).convert("RGBA")
    crop_box = tuple(probe["crop_box"])
    cropped = original.crop(crop_box)
    linework_layer = _layer_grid(layered, "linework")
    pressure_layer = _layer_grid(layered, "linework_pressure")
    return [
        {
            "name": "original",
            "image": _fit_panel(original),
            "summary": f"{original.width}x{original.height}",
        },
        {
            "name": "crop",
            "image": _fit_panel(cropped),
            "summary": f"box {probe['crop_box']}",
        },
        {
            "name": "luminance",
            "image": _grid_luminance(probe["luminance_grid"]),
            "summary": f"{probe['grid_width']}x{probe['grid_height']}",
        },
        {
            "name": "mass",
            "image": _grid_bool(probe["mass_mask"], fill=(60, 56, 50, 255)),
            "summary": f"cells {probe['occupied_cell_count']}",
        },
        {
            "name": "edge evidence",
            "image": _grid_edges(probe["edge_map"]),
            "summary": f"cells {probe['edge_cell_count']}",
        },
        {
            "name": "linework",
            "image": _grid_tokens(linework_layer),
            "summary": f"cells {_non_space_count(linework_layer)}",
            "path": str(motion_out / "layers" / "linework.png"),
        },
        {
            "name": "pressure",
            "image": _grid_tokens(pressure_layer, fill=(88, 42, 34, 255)),
            "summary": f"cells {_non_space_count(pressure_layer)}",
            "path": str(motion_out / "layers" / "linework_pressure.png"),
        },
        {
            "name": "glyph proof",
            "image": _fit_panel(Image.open(motion_out / "proof_128.png").convert("RGBA")),
            "summary": "composite",
            "path": str(motion_out / "proof_128.png"),
        },
    ]


def _summary(
    image_path: Path,
    motion_out: Path,
    probe: dict[str, Any],
    report: dict[str, Any],
    manifest: dict[str, Any],
    panels: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "image_path": str(image_path),
        "motion_out_dir": str(motion_out),
        "grid_width": probe["grid_width"],
        "grid_height": probe["grid_height"],
        "crop_box": probe["crop_box"],
        "panels": [
            {key: value for key, value in panel.items() if key not in {"image"}}
            for panel in panels
        ],
        "counts": {
            "occupied_cell_count": probe["occupied_cell_count"],
            "edge_cell_count": probe["edge_cell_count"],
            "linework_cell_count": report.get("linework_cell_count", 0),
            "pressure_cell_count": report.get("pressure_cell_count", 0),
            "constraint_warning_count": len(manifest.get("constraint_warnings", [])),
        },
        "motion_profile_counts": report.get("motion_profile_counts", {}),
        "pressure_intensity_counts": report.get("pressure_intensity_counts", {}),
        "selected_token_counts": _top_counts(report.get("selected_token_counts", {})),
        "selected_pressure_token_counts": _top_counts(report.get("selected_pressure_token_counts", {})),
    }


def _render_sheet(panels: list[dict[str, Any]], summary: dict[str, Any]) -> Image.Image:
    columns = 4
    cell_w = PANEL_SIZE + PANEL_PADDING * 2
    cell_h = PANEL_SIZE + TEXT_HEIGHT
    rows = (len(panels) + columns - 1) // columns
    footer_h = 76
    sheet = Image.new("RGBA", (columns * cell_w, rows * cell_h + footer_h), (244, 241, 232, 255))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, panel in enumerate(panels):
        col = index % columns
        row = index // columns
        left = col * cell_w
        top = row * cell_h
        draw.rectangle((left, top, left + cell_w - 1, top + cell_h - 1), outline=(120, 112, 100, 255))
        draw.text((left + PANEL_PADDING, top + 6), panel["name"], fill=(30, 28, 24, 255), font=font)
        sheet.alpha_composite(panel["image"], (left + PANEL_PADDING, top + 22))
        draw.text((left + PANEL_PADDING, top + PANEL_SIZE + 28), panel["summary"], fill=(30, 28, 24, 255), font=font)

    footer_y = rows * cell_h + 8
    footer_lines = [
        f"linework {summary['counts']['linework_cell_count']}  pressure {summary['counts']['pressure_cell_count']}  warnings {summary['counts']['constraint_warning_count']}",
        f"motion {summary['motion_profile_counts']}",
        f"pressure {summary['pressure_intensity_counts']}",
        f"tokens {summary['selected_token_counts']}",
    ]
    for offset, line in enumerate(footer_lines):
        draw.text((PANEL_PADDING, footer_y + offset * 16), _short(line, 110), fill=(30, 28, 24, 255), font=font)
    return sheet


def _grid_luminance(grid: list[list[int]]) -> Image.Image:
    height = len(grid)
    width = len(grid[0]) if height else 0
    image = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    pixels = image.load()
    for y, row in enumerate(grid):
        for x, value in enumerate(row):
            pixels[x, y] = (value, value, value, 255)
    return image.resize((PANEL_SIZE, PANEL_SIZE), Image.Resampling.NEAREST)


def _grid_bool(grid: list[list[bool]], fill: tuple[int, int, int, int]) -> Image.Image:
    height = len(grid)
    width = len(grid[0]) if height else 0
    image = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    pixels = image.load()
    for y, row in enumerate(grid):
        for x, value in enumerate(row):
            if value:
                pixels[x, y] = fill
    return image.resize((PANEL_SIZE, PANEL_SIZE), Image.Resampling.NEAREST)


def _grid_edges(edge_grid: list[list[dict[str, Any]]]) -> Image.Image:
    height = len(edge_grid)
    width = len(edge_grid[0]) if height else 0
    image = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    pixels = image.load()
    colors = {
        "horizontal": (34, 32, 29, 255),
        "vertical": (88, 83, 74, 255),
        "diagonal_rise": (45, 40, 37, 255),
        "diagonal_fall": (120, 80, 44, 255),
    }
    for y, row in enumerate(edge_grid):
        for x, cell in enumerate(row):
            if cell["edge"]:
                pixels[x, y] = colors.get(cell.get("direction"), (34, 32, 29, 255))
    return image.resize((PANEL_SIZE, PANEL_SIZE), Image.Resampling.NEAREST)


def _grid_tokens(grid: list[str], fill: tuple[int, int, int, int] = (34, 32, 29, 255)) -> Image.Image:
    height = len(grid)
    width = max((len(row) for row in grid), default=0)
    image = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    pixels = image.load()
    for y, row in enumerate(grid):
        for x, token in enumerate(row):
            if token != " ":
                pixels[x, y] = fill
    return image.resize((PANEL_SIZE, PANEL_SIZE), Image.Resampling.NEAREST)


def _fit_panel(image: Image.Image) -> Image.Image:
    copy = image.copy()
    copy.thumbnail((PANEL_SIZE, PANEL_SIZE), Image.Resampling.LANCZOS)
    panel = Image.new("RGBA", (PANEL_SIZE, PANEL_SIZE), (255, 255, 255, 255))
    left = (PANEL_SIZE - copy.width) // 2
    top = (PANEL_SIZE - copy.height) // 2
    panel.alpha_composite(copy, (left, top))
    return panel


def _layer_grid(layered: dict[str, Any], name: str) -> list[str]:
    for layer in layered.get("layers", []):
        if layer.get("name") == name:
            return layer.get("grid", [])
    return [" " * int(layered.get("grid_width", 0)) for _ in range(int(layered.get("grid_height", 0)))]


def _non_space_count(grid: list[str]) -> int:
    return sum(1 for row in grid for char in row if char != " ")


def _top_counts(counts: dict[str, int], limit: int = 8) -> dict[str, int]:
    return dict(Counter(counts).most_common(limit))


def _short(value: str, length: int) -> str:
    return value if len(value) <= length else value[: length - 3] + "..."


def _load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: str | Path, payload: dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
