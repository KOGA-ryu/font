from __future__ import annotations

from pathlib import Path
from typing import Any
import colorsys
import json

from PIL import Image, ImageDraw

from .ascii_bridge import resolve_ascii_char
from .ascii_glyph_renderer import _border_median_rgb, _luminance, _median, _rgb_distance, _tint_stamp
from .atlas import load_atlas_stamps
from .foreground_mask import foreground_mask, write_foreground_mask
from .schema import load_glyphs


DEFAULT_COLOR_FAMILIES = (
    "dark",
    "brown",
    "red",
    "orange",
    "gold",
    "lime",
    "green",
    "cyan",
    "blue",
    "violet",
    "pink",
    "skin",
    "gray",
    "highlight",
)
STACK_ORDER = (
    "skin",
    "brown",
    "orange",
    "red",
    "gold",
    "lime",
    "green",
    "cyan",
    "blue",
    "violet",
    "pink",
    "gray",
    "highlight",
    "dark",
)


def render_color_family_layers(
    image_path: str | Path,
    glyphs_path: str | Path,
    atlas_path: str | Path,
    output_dir: str | Path,
    *,
    families: str | list[str] | tuple[str, ...] = "auto",
    grid_width: int = 128,
    grid_height: int = 128,
    fill_token: str = "#",
    mapping_path: str | Path | None = None,
    background_threshold: int = 28,
    min_cell_coverage: float = 0.18,
    foreground_mode: str = "auto",
    foreground_alpha_threshold: int = 1,
    foreground_background_threshold: int | None = None,
    scale: int = 2,
) -> dict[str, Any]:
    family_names = parse_families(families)
    if grid_width <= 0 or grid_height <= 0:
        raise ValueError("grid width and height must be positive")
    if not 0.0 < min_cell_coverage <= 1.0:
        raise ValueError("min cell coverage must be greater than 0 and at most 1")
    if background_threshold < 0:
        raise ValueError("background threshold must be non-negative")
    if scale < 1:
        raise ValueError("scale must be at least 1")

    output = Path(output_dir)
    masks_dir = output / "masks"
    black_dir = output / "black"
    color_dir = output / "colorized"
    composites_dir = output / "composites"
    for directory in (masks_dir, black_dir, color_dir, composites_dir):
        directory.mkdir(parents=True, exist_ok=True)

    glyphs = load_glyphs(glyphs_path)
    stamps = load_atlas_stamps(atlas_path, glyphs)
    mapping = _load_json(mapping_path) if mapping_path is not None else None
    token = _resolve_token(fill_token, mapping, set(stamps))
    if token is None or token not in stamps:
        raise ValueError(f"unknown color-family fill token {fill_token!r}")
    stamp = stamps[token]

    with Image.open(image_path) as source:
        source_image = source.convert("RGBA")
    background = _border_median_rgb(source_image.resize((grid_width, grid_height), Image.Resampling.BOX))
    foreground, foreground_summary = foreground_mask(
        source_image,
        grid_width,
        grid_height,
        mode=foreground_mode,
        alpha_threshold=foreground_alpha_threshold,
        background_threshold=foreground_background_threshold if foreground_background_threshold is not None else background_threshold,
    )
    foreground_mask_path = masks_dir / "foreground_mask.png"
    write_foreground_mask(foreground, foreground_mask_path, scale=scale)
    grids = _family_grids(
        source_image,
        family_names,
        grid_width,
        grid_height,
        background,
        background_threshold,
        min_cell_coverage,
        foreground,
        foreground_summary["mode"] != "alpha",
    )

    layers = []
    rendered_color_layers: dict[str, Image.Image] = {}
    for family in family_names:
        grid = grids[family]
        mask = [[cell["count"] > 0 for cell in row] for row in grid]
        family_count = _mask_count(mask)
        mask_path = masks_dir / f"{family}_mask.png"
        black_path = black_dir / f"{family}_black.png"
        color_path = color_dir / f"{family}_color.png"
        _write_mask(mask, mask_path, scale=scale)
        black_image = _render_mask_layer(mask, stamp, (0, 0, 0))
        color_image = _render_color_grid_layer(grid, stamp)
        rendered_color_layers[family] = color_image
        _save_scaled(black_image, black_path, scale)
        _save_scaled(color_image, color_path, scale)
        average_rgb = _average_family_rgb(grid)
        layers.append(
            {
                "family": family,
                "cells": family_count,
                "average_rgb": list(average_rgb) if average_rgb else None,
                "average_hex": _hex_rgb(average_rgb) if average_rgb else None,
                "mask": str(mask_path),
                "black_layer": str(black_path),
                "colorized_layer": str(color_path),
            }
        )

    stack = Image.new("RGBA", (grid_width * stamp.width, grid_height * stamp.height), (255, 255, 255, 255))
    stack_order = [family for family in STACK_ORDER if family in rendered_color_layers]
    stack_order.extend(family for family in family_names if family not in stack_order)
    for family in stack_order:
        stack.alpha_composite(rendered_color_layers[family])
    stacked_path = composites_dir / "stacked_color_families.png"
    _save_scaled(stack, stacked_path, scale)
    contact_sheet_path = output / "color_family_layers_contact_sheet.png"
    _write_contact_sheet(image_path, layers, stacked_path, contact_sheet_path)

    manifest = {
        "source_image": str(image_path),
        "glyphs": str(glyphs_path),
        "atlas": str(atlas_path),
        "mapping": str(mapping_path) if mapping_path is not None else None,
        "grid_width": grid_width,
        "grid_height": grid_height,
        "families": family_names,
        "stack_order": stack_order,
        "fill_token": fill_token,
        "resolved_token": token,
        "background_rgb": list(background),
        "background_threshold": background_threshold,
        "foreground": {**foreground_summary, "mask": str(foreground_mask_path)},
        "min_cell_coverage": min_cell_coverage,
        "rule": "foreground mask is applied first; pixels are assigned to generic color families by hue, saturation, luminance, and background distance; no object labels are inferred",
        "layers": layers,
        "stacked": str(stacked_path),
        "contact_sheet": str(contact_sheet_path),
    }
    _write_json(output / "manifest.json", manifest)
    return manifest


def parse_families(value: str | list[str] | tuple[str, ...]) -> list[str]:
    if value == "auto":
        return list(DEFAULT_COLOR_FAMILIES)
    if isinstance(value, str):
        families = [part.strip() for part in value.split(",") if part.strip()]
    else:
        families = [str(part).strip() for part in value if str(part).strip()]
    if not families:
        raise ValueError("families must contain at least one value")
    unknown = [family for family in families if family not in DEFAULT_COLOR_FAMILIES]
    if unknown:
        raise ValueError(f"unknown color families {unknown!r}; expected auto or {list(DEFAULT_COLOR_FAMILIES)!r}")
    if len(families) != len(set(families)):
        raise ValueError("families must be unique")
    return families


def classify_color_family(
    rgb: tuple[int, int, int],
    *,
    background_rgb: tuple[int, int, int],
    background_threshold: int = 28,
) -> str | None:
    if _rgb_distance(rgb, background_rgb) <= background_threshold:
        return None
    luminance = _luminance(rgb)
    hue, saturation, value = _hsv(rgb)
    if luminance < 36 or (luminance < 58 and saturation < 0.25):
        return "dark"
    if saturation < 0.16:
        return "highlight" if luminance >= 195 and _rgb_distance(rgb, background_rgb) > background_threshold else "gray"
    if (hue <= 14 or hue >= 345) and saturation >= 0.28:
        return "red"
    if 14 < hue <= 38 and saturation >= 0.45 and 75 <= luminance < 166:
        return "orange"
    if 40 <= hue <= 58 and saturation >= 0.45 and luminance >= 120:
        return "gold"
    if 58 < hue < 75 and saturation >= 0.18:
        return "lime"
    if 75 <= hue < 165 and saturation >= 0.18:
        return "green"
    if 165 <= hue < 190 and saturation >= 0.18:
        return "cyan"
    if 190 <= hue <= 255 and saturation >= 0.18:
        return "blue"
    if 255 < hue <= 320 and saturation >= 0.18:
        return "violet"
    if 320 < hue < 345 and saturation >= 0.18:
        return "pink"
    if 15 <= hue <= 42 and 0.18 <= saturation <= 0.66 and luminance >= 150:
        return "skin"
    if 12 <= hue <= 58 and saturation >= 0.16:
        return "brown"
    if luminance >= 205 and value >= 0.72:
        return "highlight"
    if saturation < 0.24:
        return "gray"
    return None


def _family_grids(
    image: Image.Image,
    families: list[str],
    grid_width: int,
    grid_height: int,
    background: tuple[int, int, int],
    background_threshold: int,
    min_cell_coverage: float,
    foreground: list[list[bool]],
    use_background_filter: bool,
) -> dict[str, list[list[dict[str, Any]]]]:
    grids = {
        family: [[{"count": 0, "rgb": None} for _ in range(grid_width)] for _ in range(grid_height)]
        for family in families
    }
    pixels = image.load()
    for grid_y in range(grid_height):
        y0, y1 = _source_span(grid_y, grid_height, image.height)
        for grid_x in range(grid_width):
            if not foreground[grid_y][grid_x]:
                continue
            x0, x1 = _source_span(grid_x, grid_width, image.width)
            counts: dict[str, list[tuple[int, int, int]]] = {family: [] for family in families}
            occupied_pixels = 0
            for y in range(y0, y1):
                for x in range(x0, x1):
                    red, green, blue, alpha = pixels[x, y]
                    if alpha == 0:
                        continue
                    rgb = (red, green, blue)
                    if use_background_filter and _rgb_distance(rgb, background) <= background_threshold:
                        continue
                    occupied_pixels += 1
                    family = classify_color_family(
                        rgb,
                        background_rgb=background,
                        background_threshold=background_threshold if use_background_filter else -1,
                    )
                    if family in counts:
                        counts[family].append(rgb)
            minimum_pixels = max(1, int(round(occupied_pixels * min_cell_coverage))) if occupied_pixels else 1
            for family, colors in counts.items():
                if len(colors) >= minimum_pixels:
                    grids[family][grid_y][grid_x] = {
                        "count": len(colors),
                        "rgb": _median_rgb(colors),
                    }
    return grids


def _render_color_grid_layer(grid: list[list[dict[str, Any]]], stamp: Image.Image) -> Image.Image:
    grid_height = len(grid)
    grid_width = len(grid[0]) if grid_height else 0
    output = Image.new("RGBA", (grid_width * stamp.width, grid_height * stamp.height), (255, 255, 255, 0))
    for y, row in enumerate(grid):
        for x, cell in enumerate(row):
            if not cell["count"] or cell["rgb"] is None:
                continue
            output.alpha_composite(_tint_stamp(stamp, tuple(cell["rgb"])), (x * stamp.width, y * stamp.height))
    return output


def _render_mask_layer(mask: list[list[bool]], stamp: Image.Image, rgb: tuple[int, int, int]) -> Image.Image:
    grid_height = len(mask)
    grid_width = len(mask[0]) if grid_height else 0
    output = Image.new("RGBA", (grid_width * stamp.width, grid_height * stamp.height), (255, 255, 255, 0))
    tinted = _tint_stamp(stamp, rgb)
    for y, row in enumerate(mask):
        for x, keep in enumerate(row):
            if keep:
                output.alpha_composite(tinted, (x * stamp.width, y * stamp.height))
    return output


def _average_family_rgb(grid: list[list[dict[str, Any]]]) -> tuple[int, int, int] | None:
    colors = []
    for row in grid:
        for cell in row:
            if cell["count"] and cell["rgb"] is not None:
                colors.append(tuple(cell["rgb"]))
    return _median_rgb(colors) if colors else None


def _write_contact_sheet(
    image_path: str | Path,
    layers: list[dict[str, Any]],
    stacked_path: str | Path,
    output_path: str | Path,
) -> None:
    thumb = 220
    pad = 12
    label_h = 36
    columns = len(layers) + 1
    rows = 3
    sheet = Image.new("RGB", (pad + columns * (thumb + pad), pad + rows * (thumb + label_h + pad)), "white")
    draw = ImageDraw.Draw(sheet)

    def paste_cell(column: int, row: int, label: str, image: Image.Image, subtitle: str = "") -> None:
        x = pad + column * (thumb + pad)
        y = pad + row * (thumb + label_h + pad)
        draw.text((x, y), label, fill="black")
        if subtitle:
            draw.text((x, y + 15), subtitle, fill="black")
        view = image.convert("RGB")
        view.thumbnail((thumb, thumb), Image.Resampling.NEAREST)
        canvas = Image.new("RGB", (thumb, thumb), "white")
        canvas.paste(view, ((thumb - view.width) // 2, (thumb - view.height) // 2))
        sheet.paste(canvas, (x, y + label_h))
        draw.rectangle([x, y + label_h, x + thumb - 1, y + label_h + thumb - 1], outline=(210, 210, 210))

    with Image.open(image_path) as source:
        paste_cell(0, 0, "original", source.convert("RGB"))
    with Image.open(stacked_path) as stacked:
        paste_cell(0, 1, "stacked", stacked.convert("RGB"), "color families")
    paste_cell(0, 2, "rule", Image.new("RGB", (thumb, thumb), "white"), "hue/sat/luma -> family")

    for index, layer in enumerate(layers, start=1):
        family = layer["family"]
        subtitle = f"{layer['cells']} cells"
        if layer.get("average_hex"):
            subtitle += f" {layer['average_hex']}"
        with Image.open(layer["mask"]) as mask:
            paste_cell(index, 0, f"{family} mask", mask.convert("RGB"), subtitle)
        with Image.open(layer["black_layer"]) as black:
            paste_cell(index, 1, f"{family} black", black.convert("RGB"))
        with Image.open(layer["colorized_layer"]) as color:
            paste_cell(index, 2, f"{family} color", color.convert("RGB"))

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _write_mask(mask: list[list[bool]], output_path: str | Path, *, scale: int) -> None:
    height = len(mask)
    width = len(mask[0]) if height else 0
    image = Image.new("L", (width, height), 0)
    pixels = image.load()
    for y, row in enumerate(mask):
        for x, value in enumerate(row):
            pixels[x, y] = 255 if value else 0
    _save_scaled(image, output_path, scale)


def _save_scaled(image: Image.Image, output_path: str | Path, scale: int) -> None:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if scale > 1:
        image = image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST)
    image.save(output)


def _mask_count(mask: list[list[bool]]) -> int:
    return sum(1 for row in mask for value in row if value)


def _median_rgb(colors: list[tuple[int, int, int]]) -> tuple[int, int, int]:
    return tuple(_median([color[channel] for color in colors]) for channel in range(3))


def _hex_rgb(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def _hsv(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    red, green, blue = (channel / 255.0 for channel in rgb)
    hue, saturation, value = colorsys.rgb_to_hsv(red, green, blue)
    return hue * 360.0, saturation, value


def _source_span(index: int, grid_size: int, source_size: int) -> tuple[int, int]:
    start = int(index * source_size / grid_size)
    end = int((index + 1) * source_size / grid_size)
    if end <= start:
        end = start + 1
    return max(0, start), min(source_size, end)


def _resolve_token(char: str, mapping: dict[str, Any] | None, active_tokens: set[str]) -> str | None:
    if char in active_tokens:
        return char
    if mapping is None:
        return None
    resolved = resolve_ascii_char(char, mapping, active_tokens)
    return resolved["token"] if resolved else None


def _load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: str | Path, payload: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
