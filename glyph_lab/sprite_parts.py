from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from PIL import Image, ImageDraw

from .ascii_glyph_renderer import _border_median_rgb, _luminance, _median, _rgb_distance
from .color_family_layers import classify_color_family
from .foreground_mask import FOREGROUND_MODES, foreground_mask, write_foreground_mask


DEFAULT_PARTS = ("outline", "hair", "skin", "clothing", "leather", "metal", "gold", "highlight")
PART_STACK_ORDER = ("skin", "hair", "leather", "clothing", "metal", "gold", "highlight", "outline")
PART_COLORS = {
    "outline": (0, 0, 0),
    "hair": (92, 55, 25),
    "skin": (226, 163, 92),
    "clothing": (40, 72, 140),
    "leather": (112, 68, 28),
    "metal": (128, 138, 142),
    "gold": (210, 160, 45),
    "highlight": (235, 235, 225),
}


def classify_sprite_parts(
    image_path: str | Path,
    output_dir: str | Path,
    *,
    grid_width: int = 128,
    grid_height: int = 128,
    foreground_mode: str = "auto",
    foreground_alpha_threshold: int = 1,
    foreground_background_threshold: int = 28,
    background_threshold: int = 28,
    min_cell_coverage: float = 0.14,
    scale: int = 2,
) -> dict[str, Any]:
    if grid_width <= 0 or grid_height <= 0:
        raise ValueError("grid width and height must be positive")
    if foreground_mode not in FOREGROUND_MODES:
        raise ValueError(f"unknown foreground mode {foreground_mode!r}; expected one of {sorted(FOREGROUND_MODES)}")
    if not 0.0 < min_cell_coverage <= 1.0:
        raise ValueError("min cell coverage must be greater than 0 and at most 1")
    if scale < 1:
        raise ValueError("scale must be at least 1")

    output = Path(output_dir)
    masks_dir = output / "masks"
    color_dir = output / "colorized"
    composites_dir = output / "composites"
    for directory in (masks_dir, color_dir, composites_dir):
        directory.mkdir(parents=True, exist_ok=True)

    with Image.open(image_path) as source:
        source_image = source.convert("RGBA")
    sampled = source_image.resize((grid_width, grid_height), Image.Resampling.BOX)
    background = _border_median_rgb(sampled)
    foreground, foreground_summary = foreground_mask(
        source_image,
        grid_width,
        grid_height,
        mode=foreground_mode,
        alpha_threshold=foreground_alpha_threshold,
        background_threshold=foreground_background_threshold,
    )
    foreground_mask_path = masks_dir / "foreground_mask.png"
    write_foreground_mask(foreground, foreground_mask_path, scale=scale)
    occupied_bbox = _mask_bbox(foreground)

    family_grid = _sample_family_grid(
        source_image,
        grid_width,
        grid_height,
        foreground,
        background,
        background_threshold,
        min_cell_coverage,
        foreground_summary["mode"] != "alpha",
    )
    part_grid = _classify_part_grid(family_grid, occupied_bbox)
    masks = {
        part: [[part_grid[y][x]["part"] == part for x in range(grid_width)] for y in range(grid_height)]
        for part in DEFAULT_PARTS
    }

    layers = []
    rendered_layers: dict[str, Image.Image] = {}
    for part in DEFAULT_PARTS:
        mask = masks[part]
        mask_path = masks_dir / f"{part}_mask.png"
        color_path = color_dir / f"{part}_color.png"
        _write_mask(mask, mask_path, scale=scale)
        color_image = _render_part_layer(part_grid, part)
        rendered_layers[part] = color_image
        _save_scaled(color_image, color_path, scale)
        components = _connected_components(mask)
        layers.append(
            {
                "part": part,
                "cells": _mask_count(mask),
                "average_rgb": list(_average_part_rgb(part_grid, part)) if _average_part_rgb(part_grid, part) else None,
                "average_hex": _hex_rgb(_average_part_rgb(part_grid, part)),
                "mask": str(mask_path),
                "colorized_layer": str(color_path),
                "components": components,
            }
        )

    stack = Image.new("RGBA", (grid_width, grid_height), (255, 255, 255, 255))
    for part in PART_STACK_ORDER:
        stack.alpha_composite(rendered_layers[part])
    stacked_path = composites_dir / "stacked_sprite_parts.png"
    _save_scaled(stack, stacked_path, scale)
    contact_sheet_path = output / "sprite_part_contact_sheet.png"

    manifest = {
        "source_image": str(image_path),
        "grid_width": grid_width,
        "grid_height": grid_height,
        "background_rgb": list(background),
        "background_threshold": background_threshold,
        "foreground": {**foreground_summary, "mask": str(foreground_mask_path)},
        "occupied_bbox_cells": list(occupied_bbox) if occupied_bbox else None,
        "parts": list(DEFAULT_PARTS),
        "stack_order": list(PART_STACK_ORDER),
        "rule": "generic humanoid sprite parts from color-family evidence plus occupied-bbox geometry; no one-off object labels",
        "layers": layers,
        "stacked": str(stacked_path),
        "contact_sheet": str(contact_sheet_path),
    }
    _write_contact_sheet(image_path, manifest, contact_sheet_path)
    _write_json(output / "sprite_part_layers.json", manifest)
    return manifest


def _sample_family_grid(
    image: Image.Image,
    grid_width: int,
    grid_height: int,
    foreground: list[list[bool]],
    background: tuple[int, int, int],
    background_threshold: int,
    min_cell_coverage: float,
    use_background_filter: bool,
) -> list[list[dict[str, Any]]]:
    pixels = image.load()
    grid = [[{"family": None, "rgb": None, "luminance": None} for _ in range(grid_width)] for _ in range(grid_height)]
    for grid_y in range(grid_height):
        y0, y1 = _source_span(grid_y, grid_height, image.height)
        for grid_x in range(grid_width):
            if not foreground[grid_y][grid_x]:
                continue
            x0, x1 = _source_span(grid_x, grid_width, image.width)
            colors = []
            for y in range(y0, y1):
                for x in range(x0, x1):
                    red, green, blue, alpha = pixels[x, y]
                    if alpha == 0:
                        continue
                    rgb = (red, green, blue)
                    if use_background_filter and _rgb_distance(rgb, background) <= background_threshold:
                        continue
                    colors.append(rgb)
            if len(colors) < max(1, int(round((x1 - x0) * (y1 - y0) * min_cell_coverage))):
                continue
            rgb = tuple(_median([color[channel] for color in colors]) for channel in range(3))
            grid[grid_y][grid_x] = {
                "family": classify_color_family(
                    rgb,
                    background_rgb=background,
                    background_threshold=background_threshold if use_background_filter else -1,
                ),
                "rgb": rgb,
                "luminance": _luminance(rgb),
            }
    return grid


def _classify_part_grid(
    family_grid: list[list[dict[str, Any]]],
    occupied_bbox: tuple[int, int, int, int] | None,
) -> list[list[dict[str, Any]]]:
    height = len(family_grid)
    width = len(family_grid[0]) if height else 0
    output = [[{**family_grid[y][x], "part": None} for x in range(width)] for y in range(height)]
    if occupied_bbox is None:
        return output
    x0, y0, x1, y1 = occupied_bbox
    occupied_h = max(1, y1 - y0 + 1)
    upper_cut = y0 + int(occupied_h * 0.35)
    torso_cut = y0 + int(occupied_h * 0.68)

    skin_bbox = _family_bbox(family_grid, "skin", max_y=y0 + int(occupied_h * 0.46))
    if skin_bbox is not None:
        _, skin_y0, _, skin_y1 = skin_bbox
        head_bottom = skin_y1 + max(2, int(occupied_h * 0.08))
    else:
        head_bottom = upper_cut

    for y, row in enumerate(family_grid):
        for x, cell in enumerate(row):
            family = cell["family"]
            if family is None:
                continue
            part = _part_for_cell(family, x, y, y0, upper_cut, torso_cut, head_bottom)
            output[y][x]["part"] = part
    return output


def _part_for_cell(
    family: str,
    x: int,
    y: int,
    occupied_top: int,
    upper_cut: int,
    torso_cut: int,
    head_bottom: int,
) -> str | None:
    if family == "dark":
        return "outline"
    if family == "skin":
        return "skin"
    if family in {"blue", "violet", "green", "lime", "cyan", "red", "orange", "pink"}:
        return "clothing"
    if family == "gray":
        return "metal" if y < occupied_top + 0.88 * (torso_cut - occupied_top + 1) or x < 0 else "metal"
    if family == "gold":
        return "gold"
    if family == "highlight":
        return "highlight"
    if family == "brown":
        return "hair" if y <= max(upper_cut, head_bottom) else "leather"
    return None


def _family_bbox(
    grid: list[list[dict[str, Any]]],
    family: str,
    *,
    max_y: int | None = None,
) -> tuple[int, int, int, int] | None:
    points = [
        (x, y)
        for y, row in enumerate(grid)
        for x, cell in enumerate(row)
        if cell["family"] == family and (max_y is None or y <= max_y)
    ]
    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def _mask_bbox(mask: list[list[bool]]) -> tuple[int, int, int, int] | None:
    points = [(x, y) for y, row in enumerate(mask) for x, value in enumerate(row) if value]
    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def _render_part_layer(part_grid: list[list[dict[str, Any]]], part: str) -> Image.Image:
    height = len(part_grid)
    width = len(part_grid[0]) if height else 0
    image = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    pixels = image.load()
    for y, row in enumerate(part_grid):
        for x, cell in enumerate(row):
            if cell["part"] != part or cell["rgb"] is None:
                continue
            pixels[x, y] = (*cell["rgb"], 255)
    return image


def _connected_components(mask: list[list[bool]]) -> list[dict[str, Any]]:
    height = len(mask)
    width = len(mask[0]) if height else 0
    seen = [[False for _ in range(width)] for _ in range(height)]
    components = []
    for y in range(height):
        for x in range(width):
            if seen[y][x] or not mask[y][x]:
                continue
            stack = [(x, y)]
            seen[y][x] = True
            cells = []
            while stack:
                cx, cy = stack.pop()
                cells.append((cx, cy))
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if 0 <= nx < width and 0 <= ny < height and not seen[ny][nx] and mask[ny][nx]:
                        seen[ny][nx] = True
                        stack.append((nx, ny))
            xs = [cell[0] for cell in cells]
            ys = [cell[1] for cell in cells]
            components.append(
                {
                    "cells": len(cells),
                    "bbox": [min(xs), min(ys), max(xs), max(ys)],
                }
            )
    components.sort(key=lambda item: item["cells"], reverse=True)
    return components


def _average_part_rgb(part_grid: list[list[dict[str, Any]]], part: str) -> tuple[int, int, int] | None:
    colors = [cell["rgb"] for row in part_grid for cell in row if cell["part"] == part and cell["rgb"] is not None]
    if not colors:
        return None
    return tuple(_median([color[channel] for color in colors]) for channel in range(3))


def _write_mask(mask: list[list[bool]], output_path: str | Path, *, scale: int) -> None:
    height = len(mask)
    width = len(mask[0]) if height else 0
    image = Image.new("L", (width, height), 0)
    pixels = image.load()
    for y, row in enumerate(mask):
        for x, value in enumerate(row):
            pixels[x, y] = 255 if value else 0
    _save_scaled(image, output_path, scale)


def _write_contact_sheet(image_path: str | Path, manifest: dict[str, Any], output_path: str | Path) -> None:
    layers = [layer for layer in manifest["layers"] if layer["cells"] > 0]
    thumb = 190
    pad = 12
    label_h = 36
    cells = [("original", str(image_path), ""), ("stacked", manifest["stacked"], "sprite parts")]
    cells.extend((layer["part"], layer["colorized_layer"], f"{layer['cells']} cells {layer['average_hex'] or ''}") for layer in layers)
    columns = 5
    rows = max(1, (len(cells) + columns - 1) // columns)
    sheet = Image.new("RGB", (pad + columns * (thumb + pad), pad + rows * (thumb + label_h + pad)), "white")
    draw = ImageDraw.Draw(sheet)
    for index, (label, path, subtitle) in enumerate(cells):
        column = index % columns
        row = index // columns
        x = pad + column * (thumb + pad)
        y = pad + row * (thumb + label_h + pad)
        draw.text((x, y), label, fill="black")
        if subtitle:
            draw.text((x, y + 15), subtitle[:32], fill="black")
        with Image.open(path) as image:
            view = image.convert("RGB")
            view.thumbnail((thumb, thumb), Image.Resampling.NEAREST)
            canvas = Image.new("RGB", (thumb, thumb), "white")
            canvas.paste(view, ((thumb - view.width) // 2, (thumb - view.height) // 2))
            sheet.paste(canvas, (x, y + label_h))
        draw.rectangle([x, y + label_h, x + thumb - 1, y + label_h + thumb - 1], outline=(210, 210, 210))
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _source_span(index: int, grid_size: int, source_size: int) -> tuple[int, int]:
    start = int(index * source_size / grid_size)
    end = int((index + 1) * source_size / grid_size)
    if end <= start:
        end = start + 1
    return max(0, start), min(source_size, end)


def _mask_count(mask: list[list[bool]]) -> int:
    return sum(1 for row in mask for value in row if value)


def _hex_rgb(rgb: tuple[int, int, int] | None) -> str | None:
    return None if rgb is None else "#" + "".join(f"{channel:02x}" for channel in rgb)


def _save_scaled(image: Image.Image, output_path: str | Path, scale: int) -> None:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if scale > 1:
        image = image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST)
    image.save(output)


def _write_json(path: str | Path, payload: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
