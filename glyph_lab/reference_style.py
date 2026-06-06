from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any
import json

from PIL import Image

from .ascii_glyph_renderer import _border_median_rgb, _luminance, _rgb_distance
from .color_family_layers import DEFAULT_COLOR_FAMILIES, classify_color_family, parse_families
from .foreground_mask import foreground_mask


DEFAULT_STYLE_PALETTE_SIZE = 3
DEFAULT_OUTLINE_THRESHOLD = 48

GLYPH_PACKAGE_BY_LAYER = {
    "outline": "solid_dots",
    "dark": "shadow_dots",
    "brown": "grain_fill",
    "skin": "flat_fill",
    "highlight": "sparse_highlight",
    "gray": "flat_fill",
}


def build_reference_style_recipe(
    image_path: str | Path,
    output_path: str | Path,
    *,
    grid_width: int = 128,
    grid_height: int = 128,
    families: str | list[str] | tuple[str, ...] = "auto",
    palette_size: int = DEFAULT_STYLE_PALETTE_SIZE,
    outline_threshold: int = DEFAULT_OUTLINE_THRESHOLD,
    background_threshold: int = 28,
    foreground_mode: str = "auto",
    foreground_alpha_threshold: int = 1,
    foreground_background_threshold: int | None = None,
    fill_token: str = "#",
    min_layer_cells: int = 1,
) -> dict[str, Any]:
    if grid_width <= 0 or grid_height <= 0:
        raise ValueError("grid width and height must be positive")
    if palette_size < 1:
        raise ValueError("palette size must be at least 1")
    if not 0 <= outline_threshold <= 255:
        raise ValueError("outline threshold must be between 0 and 255")
    if background_threshold < 0:
        raise ValueError("background threshold must be non-negative")
    if min_layer_cells < 1:
        raise ValueError("minimum layer cells must be at least 1")

    family_names = parse_families(families)
    source_path = Path(image_path)
    output_file = _output_file(output_path)
    with Image.open(source_path) as source:
        image = source.convert("RGBA")

    sampled = image.resize((grid_width, grid_height), Image.Resampling.BOX)
    background = _border_median_rgb(sampled)
    foreground, foreground_summary = foreground_mask(
        image,
        grid_width,
        grid_height,
        mode=foreground_mode,
        alpha_threshold=foreground_alpha_threshold,
        background_threshold=foreground_background_threshold
        if foreground_background_threshold is not None
        else background_threshold,
    )
    use_background_filter = foreground_summary["mode"] != "alpha"
    evidence = _collect_evidence(
        image,
        foreground,
        family_names,
        background,
        background_threshold,
        outline_threshold,
        use_background_filter,
    )

    layers = []
    outline = evidence["outline"]
    if outline["cells"] >= min_layer_cells:
        layers.append(
            {
                "name": "outline",
                "role": "linework",
                "mask_source": f"threshold:black<{outline_threshold}",
                "glyph_package": "solid_dots",
                "palette": ["#000000"],
                "coverage": 1.0,
                "cell_count": outline["cells"],
                "pixel_count": outline["pixels"],
                "notes": "geometry from dark threshold; color is forced black",
            }
        )

    for family in family_names:
        family_evidence = evidence["families"][family]
        if family_evidence["cells"] < min_layer_cells:
            continue
        palette = reduce_palette(family_evidence["colors"], palette_size)
        layers.append(
            {
                "name": family,
                "role": _role_for_family(family),
                "mask_source": f"color_family:{family}",
                "glyph_package": _glyph_package_for_family(family),
                "palette": [_hex_rgb(color) for color in palette],
                "coverage": _coverage_for_family(family),
                "cell_count": family_evidence["cells"],
                "pixel_count": family_evidence["pixels"],
                "notes": "palette is reduced from source evidence; not an exact RGB copy",
            }
        )

    recipe = {
        "schema": "glyph_lab.reference_style_recipe.v0",
        "source_image": str(source_path),
        "style_intent": "reference_interpreter_not_replica",
        "canvas": {"grid_width": grid_width, "grid_height": grid_height, "fill_token": fill_token},
        "foreground": foreground_summary,
        "background_rgb": list(background),
        "background_threshold": background_threshold,
        "palette_size": palette_size,
        "outline_threshold": outline_threshold,
        "layers": layers,
        "generation_controls": {
            "editable": True,
            "safe_to_mutate": ["palette", "coverage", "glyph_package", "mask_source", "layer_order"],
            "pipeline": [
                "reference image",
                "foreground mask",
                "threshold/color-family evidence",
                "reduced palettes",
                "glyph package assignment",
                "editable generation recipe",
            ],
        },
    }
    _write_json(output_file, recipe)
    return recipe


def reduce_palette(colors: list[tuple[int, int, int]], palette_size: int) -> list[tuple[int, int, int]]:
    if palette_size < 1:
        raise ValueError("palette size must be at least 1")
    counts = Counter(colors)
    if not counts:
        return []
    if len(counts) <= palette_size:
        return sorted(counts, key=lambda color: (-counts[color], _luminance(color), color))

    buckets: list[list[tuple[tuple[int, int, int], int]]] = [[(color, count) for color, count in counts.items()]]
    while len(buckets) < palette_size:
        index = _bucket_to_split(buckets)
        bucket = buckets.pop(index)
        left, right = _split_bucket(bucket)
        buckets.extend([left, right])
        if all(len(bucket) == 1 for bucket in buckets):
            break

    palette = [_weighted_average(bucket) for bucket in buckets]
    return sorted(palette, key=lambda color: (_luminance(color), color))


def _collect_evidence(
    image: Image.Image,
    foreground: list[list[bool]],
    families: list[str],
    background: tuple[int, int, int],
    background_threshold: int,
    outline_threshold: int,
    use_background_filter: bool,
) -> dict[str, Any]:
    grid_height = len(foreground)
    grid_width = len(foreground[0]) if grid_height else 0
    pixels = image.load()
    family_cells = {family: set() for family in families}
    family_colors = {family: [] for family in families}
    outline_cells = set()
    outline_pixels = 0
    family_pixels = {family: 0 for family in families}

    for grid_y in range(grid_height):
        y0, y1 = _source_span(grid_y, grid_height, image.height)
        for grid_x in range(grid_width):
            if not foreground[grid_y][grid_x]:
                continue
            x0, x1 = _source_span(grid_x, grid_width, image.width)
            for y in range(y0, y1):
                for x in range(x0, x1):
                    red, green, blue, alpha = pixels[x, y]
                    if alpha == 0:
                        continue
                    rgb = (red, green, blue)
                    if use_background_filter and _rgb_distance(rgb, background) <= background_threshold:
                        continue
                    if _luminance(rgb) < outline_threshold:
                        outline_cells.add((grid_x, grid_y))
                        outline_pixels += 1
                    family = classify_color_family(
                        rgb,
                        background_rgb=background,
                        background_threshold=background_threshold if use_background_filter else -1,
                    )
                    if family in family_cells:
                        family_cells[family].add((grid_x, grid_y))
                        family_colors[family].append(rgb)
                        family_pixels[family] += 1

    return {
        "outline": {"cells": len(outline_cells), "pixels": outline_pixels},
        "families": {
            family: {
                "cells": len(family_cells[family]),
                "pixels": family_pixels[family],
                "colors": family_colors[family],
            }
            for family in families
        },
    }


def _glyph_package_for_family(family: str) -> str:
    if family in GLYPH_PACKAGE_BY_LAYER:
        return GLYPH_PACKAGE_BY_LAYER[family]
    if family in DEFAULT_COLOR_FAMILIES:
        return "flat_fill"
    return "generic_fill"


def _role_for_family(family: str) -> str:
    if family == "dark":
        return "shadow"
    if family == "highlight":
        return "highlight"
    return "color_fill"


def _coverage_for_family(family: str) -> float:
    if family == "highlight":
        return 0.45
    if family in {"dark", "gray", "brown"}:
        return 0.75
    return 0.85


def _bucket_to_split(buckets: list[list[tuple[tuple[int, int, int], int]]]) -> int:
    best_index = 0
    best_score = -1
    for index, bucket in enumerate(buckets):
        if len(bucket) <= 1:
            continue
        ranges = _bucket_ranges(bucket)
        score = max(ranges) * sum(count for _, count in bucket)
        if score > best_score:
            best_index = index
            best_score = score
    return best_index


def _split_bucket(
    bucket: list[tuple[tuple[int, int, int], int]],
) -> tuple[list[tuple[tuple[int, int, int], int]], list[tuple[tuple[int, int, int], int]]]:
    ranges = _bucket_ranges(bucket)
    channel = ranges.index(max(ranges))
    ordered = sorted(bucket, key=lambda item: (item[0][channel], item[0]))
    total = sum(count for _, count in ordered)
    midpoint = total / 2
    running = 0
    split_at = 1
    for index, (_, count) in enumerate(ordered, start=1):
        running += count
        if running >= midpoint:
            split_at = min(max(1, index), len(ordered) - 1)
            break
    return ordered[:split_at], ordered[split_at:]


def _bucket_ranges(bucket: list[tuple[tuple[int, int, int], int]]) -> tuple[int, int, int]:
    return tuple(max(color[channel] for color, _ in bucket) - min(color[channel] for color, _ in bucket) for channel in range(3))


def _weighted_average(bucket: list[tuple[tuple[int, int, int], int]]) -> tuple[int, int, int]:
    total = sum(count for _, count in bucket)
    return tuple(int(round(sum(color[channel] * count for color, count in bucket) / total)) for channel in range(3))


def _source_span(index: int, grid_size: int, source_size: int) -> tuple[int, int]:
    start = int(index * source_size / grid_size)
    end = int((index + 1) * source_size / grid_size)
    if end <= start:
        end = start + 1
    return max(0, start), min(source_size, end)


def _output_file(output_path: str | Path) -> Path:
    path = Path(output_path)
    if path.suffix.lower() == ".json":
        return path
    return path / "reference_style_recipe.json"


def _hex_rgb(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
