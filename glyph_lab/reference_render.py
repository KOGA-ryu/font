from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from PIL import Image

from .ascii_bridge import resolve_ascii_char
from .ascii_glyph_renderer import _border_median_rgb, _luminance, _median, _rgb_distance, _tint_stamp
from .atlas import load_atlas_stamps
from .color_family_layers import classify_color_family
from .foreground_mask import foreground_mask
from .schema import load_glyphs


def render_reference_style(
    recipe_path: str | Path,
    output_dir: str | Path,
    glyphs_path: str | Path,
    atlas_path: str | Path,
    *,
    mapping_path: str | Path | None = None,
    scale: int = 2,
) -> dict[str, Any]:
    if scale < 1:
        raise ValueError("scale must be at least 1")
    recipe_file = Path(recipe_path)
    recipe = _load_json(recipe_file)
    if recipe.get("schema") != "glyph_lab.reference_style_recipe.v0":
        raise ValueError("reference style renderer requires glyph_lab.reference_style_recipe.v0")

    output = Path(output_dir)
    masks_dir = output / "masks"
    layers_dir = output / "layers"
    for directory in (masks_dir, layers_dir):
        directory.mkdir(parents=True, exist_ok=True)

    source_path = _resolve_recipe_path(recipe_file.parent, recipe["source_image"])
    with Image.open(source_path) as source:
        source_image = source.convert("RGBA")

    canvas = recipe.get("canvas", {})
    grid_width = int(canvas.get("grid_width", 128))
    grid_height = int(canvas.get("grid_height", 128))
    if grid_width <= 0 or grid_height <= 0:
        raise ValueError("recipe canvas grid dimensions must be positive")

    glyphs = load_glyphs(glyphs_path)
    stamps = load_atlas_stamps(atlas_path, glyphs)
    mapping = _load_json(mapping_path) if mapping_path is not None else None
    fill_token = str(canvas.get("fill_token", "#"))
    token = _resolve_token(fill_token, mapping, set(stamps))
    if token is None or token not in stamps:
        raise ValueError(f"unknown reference style fill token {fill_token!r}")
    stamp = stamps[token]

    foreground_config = recipe.get("foreground", {})
    foreground, foreground_summary = foreground_mask(
        source_image,
        grid_width,
        grid_height,
        mode=foreground_config.get("mode", "auto"),
        alpha_threshold=int(foreground_config.get("alpha_threshold", 1)),
        background_threshold=int(foreground_config.get("background_threshold", recipe.get("background_threshold", 28))),
    )
    background = tuple(recipe.get("background_rgb") or _border_median_rgb(source_image.resize((grid_width, grid_height), Image.Resampling.BOX)))
    if len(background) != 3:
        raise ValueError("recipe background_rgb must contain three values")
    background_rgb = (int(background[0]), int(background[1]), int(background[2]))
    use_background_filter = foreground_summary["mode"] != "alpha"
    background_threshold = int(recipe.get("background_threshold", foreground_summary.get("background_threshold", 28)))

    rendered_layers = []
    layer_images: dict[str, Image.Image] = {}
    for layer in recipe.get("layers", []):
        name = _required_layer_name(layer)
        palette = _parse_palette(layer.get("palette"))
        if not palette:
            continue
        coverage = float(layer.get("coverage", 1.0))
        if not 0.0 <= coverage <= 1.0:
            raise ValueError(f"layer {name!r} coverage must be between 0.0 and 1.0")
        mask, color_grid = _resolve_layer_evidence(
            source_image,
            foreground,
            layer.get("mask_source"),
            palette,
            background_rgb,
            background_threshold,
            use_background_filter,
        )
        thinned_mask = _apply_coverage(mask, coverage, name)
        mask_path = masks_dir / f"{name}_mask.png"
        layer_path = layers_dir / f"{name}.png"
        _write_mask(thinned_mask, mask_path, scale=scale)
        image = _render_layer(thinned_mask, color_grid, palette, stamp)
        layer_images[name] = image
        _save_scaled(image, layer_path, scale)
        rendered_layers.append(
            {
                "name": name,
                "role": layer.get("role"),
                "glyph_package": layer.get("glyph_package"),
                "mask_source": layer.get("mask_source"),
                "palette": [_hex_rgb(color) for color in palette],
                "coverage": coverage,
                "mask": str(mask_path),
                "path": str(layer_path),
                "kept_cells": _mask_count(thinned_mask),
            }
        )

    final = Image.new("RGBA", (grid_width * stamp.width, grid_height * stamp.height), (255, 255, 255, 0))
    composite_order = _composite_order([layer["name"] for layer in rendered_layers])
    for name in composite_order:
        final.alpha_composite(layer_images[name])
    final_path = output / "final.png"
    _save_scaled(final, final_path, scale)

    manifest = {
        "recipe": str(recipe_file),
        "source_image": str(source_path),
        "glyphs": str(glyphs_path),
        "atlas": str(atlas_path),
        "mapping": str(mapping_path) if mapping_path is not None else None,
        "grid_width": grid_width,
        "grid_height": grid_height,
        "fill_token": fill_token,
        "resolved_token": token,
        "foreground": foreground_summary,
        "composite_order": composite_order,
        "layers": rendered_layers,
        "final": str(final_path),
        "rule": "mask_source resolves geometry; recipe palette is the only allowed color set; coverage is deterministic",
    }
    _write_json(output / "render_manifest.json", manifest)
    return manifest


def _resolve_layer_evidence(
    image: Image.Image,
    foreground: list[list[bool]],
    mask_source: Any,
    palette: list[tuple[int, int, int]],
    background_rgb: tuple[int, int, int],
    background_threshold: int,
    use_background_filter: bool,
) -> tuple[list[list[bool]], list[list[tuple[int, int, int]]]]:
    if not isinstance(mask_source, str):
        raise ValueError("reference style layer requires a string mask_source")
    if mask_source.startswith("threshold:black<"):
        threshold = int(mask_source.removeprefix("threshold:black<"))
        return _threshold_evidence(image, foreground, threshold, palette)
    if mask_source.startswith("color_family:"):
        family = mask_source.removeprefix("color_family:")
        return _family_evidence(image, foreground, family, palette, background_rgb, background_threshold, use_background_filter)
    raise ValueError(f"unknown reference style mask_source {mask_source!r}")


def _threshold_evidence(
    image: Image.Image,
    foreground: list[list[bool]],
    threshold: int,
    palette: list[tuple[int, int, int]],
) -> tuple[list[list[bool]], list[list[tuple[int, int, int]]]]:
    grid_height = len(foreground)
    grid_width = len(foreground[0]) if grid_height else 0
    pixels = image.load()
    mask = [[False for _ in range(grid_width)] for _ in range(grid_height)]
    colors = [[palette[0] for _ in range(grid_width)] for _ in range(grid_height)]
    for grid_y in range(grid_height):
        y0, y1 = _source_span(grid_y, grid_height, image.height)
        for grid_x in range(grid_width):
            if not foreground[grid_y][grid_x]:
                continue
            x0, x1 = _source_span(grid_x, grid_width, image.width)
            candidates = []
            for y in range(y0, y1):
                for x in range(x0, x1):
                    red, green, blue, alpha = pixels[x, y]
                    if alpha == 0:
                        continue
                    rgb = (red, green, blue)
                    if _luminance(rgb) < threshold:
                        candidates.append(rgb)
            if candidates:
                mask[grid_y][grid_x] = True
                colors[grid_y][grid_x] = _nearest_rgb(_median_rgb(candidates), palette)
    return mask, colors


def _family_evidence(
    image: Image.Image,
    foreground: list[list[bool]],
    family: str,
    palette: list[tuple[int, int, int]],
    background_rgb: tuple[int, int, int],
    background_threshold: int,
    use_background_filter: bool,
) -> tuple[list[list[bool]], list[list[tuple[int, int, int]]]]:
    grid_height = len(foreground)
    grid_width = len(foreground[0]) if grid_height else 0
    pixels = image.load()
    mask = [[False for _ in range(grid_width)] for _ in range(grid_height)]
    colors = [[palette[0] for _ in range(grid_width)] for _ in range(grid_height)]
    for grid_y in range(grid_height):
        y0, y1 = _source_span(grid_y, grid_height, image.height)
        for grid_x in range(grid_width):
            if not foreground[grid_y][grid_x]:
                continue
            x0, x1 = _source_span(grid_x, grid_width, image.width)
            candidates = []
            for y in range(y0, y1):
                for x in range(x0, x1):
                    red, green, blue, alpha = pixels[x, y]
                    if alpha == 0:
                        continue
                    rgb = (red, green, blue)
                    if use_background_filter and _rgb_distance(rgb, background_rgb) <= background_threshold:
                        continue
                    if classify_color_family(
                        rgb,
                        background_rgb=background_rgb,
                        background_threshold=background_threshold if use_background_filter else -1,
                    ) == family:
                        candidates.append(rgb)
            if candidates:
                mask[grid_y][grid_x] = True
                colors[grid_y][grid_x] = _nearest_rgb(_median_rgb(candidates), palette)
    return mask, colors


def _render_layer(
    mask: list[list[bool]],
    color_grid: list[list[tuple[int, int, int]]],
    palette: list[tuple[int, int, int]],
    stamp: Image.Image,
) -> Image.Image:
    grid_height = len(mask)
    grid_width = len(mask[0]) if grid_height else 0
    output = Image.new("RGBA", (grid_width * stamp.width, grid_height * stamp.height), (255, 255, 255, 0))
    for y, row in enumerate(mask):
        for x, keep in enumerate(row):
            if not keep:
                continue
            color = _nearest_rgb(color_grid[y][x], palette)
            output.alpha_composite(_tint_stamp(stamp, color), (x * stamp.width, y * stamp.height))
    return output


def _apply_coverage(mask: list[list[bool]], coverage: float, layer_name: str) -> list[list[bool]]:
    if coverage >= 1.0:
        return [list(row) for row in mask]
    if coverage <= 0.0:
        return [[False for _ in row] for row in mask]
    result = [[False for _ in row] for row in mask]
    limit = int(round(coverage * 10000))
    for y, row in enumerate(mask):
        for x, keep in enumerate(row):
            if keep and _stable_cell_value(layer_name, x, y) < limit:
                result[y][x] = True
    return result


def _stable_cell_value(layer_name: str, x: int, y: int) -> int:
    value = 2166136261
    for byte in f"{layer_name}:{x}:{y}".encode("utf-8"):
        value ^= byte
        value = (value * 16777619) & 0xFFFFFFFF
    return value % 10000


def _composite_order(names: list[str]) -> list[str]:
    outlines = [name for name in names if name == "outline"]
    return [name for name in names if name != "outline"] + outlines


def _resolve_token(char: str, mapping: dict[str, Any] | None, active_tokens: set[str]) -> str | None:
    if char in active_tokens:
        return char
    if mapping is not None:
        resolved = resolve_ascii_char(char, mapping, active_tokens)
        if resolved is not None:
            return resolved["token"]
    return None


def _parse_palette(value: Any) -> list[tuple[int, int, int]]:
    if not isinstance(value, list):
        raise ValueError("reference style layer palette must be a list")
    return [_parse_hex_rgb(color) for color in value]


def _parse_hex_rgb(value: Any) -> tuple[int, int, int]:
    if not isinstance(value, str):
        raise ValueError(f"palette color must be #RRGGBB, got {value!r}")
    text = value.strip()
    if text.startswith("#"):
        text = text[1:]
    if len(text) != 6:
        raise ValueError(f"palette color must be #RRGGBB, got {value!r}")
    try:
        return tuple(int(text[index : index + 2], 16) for index in (0, 2, 4))
    except ValueError as exc:
        raise ValueError(f"palette color must be #RRGGBB, got {value!r}") from exc


def _median_rgb(colors: list[tuple[int, int, int]]) -> tuple[int, int, int]:
    return tuple(_median([color[channel] for color in colors]) for channel in range(3))


def _nearest_rgb(color: tuple[int, int, int], palette: list[tuple[int, int, int]]) -> tuple[int, int, int]:
    return min(palette, key=lambda palette_color: (_rgb_distance(color, palette_color), palette_color))


def _source_span(index: int, grid_size: int, source_size: int) -> tuple[int, int]:
    start = int(index * source_size / grid_size)
    end = int((index + 1) * source_size / grid_size)
    if end <= start:
        end = start + 1
    return max(0, start), min(source_size, end)


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
    if scale > 1:
        image = image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)


def _mask_count(mask: list[list[bool]]) -> int:
    return sum(1 for row in mask for value in row if value)


def _required_layer_name(layer: dict[str, Any]) -> str:
    name = layer.get("name")
    if not isinstance(name, str) or not name:
        raise ValueError("reference style layer requires a non-empty name")
    return name


def _resolve_recipe_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _hex_rgb(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def _load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: str | Path, payload: dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
