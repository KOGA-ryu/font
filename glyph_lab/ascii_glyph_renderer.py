from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any
import json

from PIL import Image

from .ascii_bridge import resolve_ascii_char
from .atlas import load_atlas_stamps
from .schema import CELL_SIZE, load_glyphs


DEFAULT_EDGE_ALIASES = {"─": "-", "│": "|"}
GATE_MODES = {"alpha", "black", "luminance", "border-difference"}


def render_ascii_glyphs(
    ascii_path: str | Path,
    glyphs_path: str | Path,
    atlas_path: str | Path,
    output_path: str | Path,
    *,
    mapping_path: str | Path | None = None,
    gate_image_path: str | Path | None = None,
    gate_mode: str = "border-difference",
    gate_threshold: int = 32,
    gate_dilate: int = 1,
    gate_mask_output_path: str | Path | None = None,
    scale: int = 4,
    background: tuple[int, int, int, int] = (255, 255, 255, 255),
) -> dict[str, Any]:
    if scale < 1:
        raise ValueError("scale must be at least 1")

    rows = Path(ascii_path).read_text(encoding="utf-8").splitlines()
    if not rows:
        raise ValueError("ASCII grid is empty")
    width = max(len(row) for row in rows)
    height = len(rows)
    if width <= 0:
        raise ValueError("ASCII grid has no columns")

    glyphs = load_glyphs(glyphs_path)
    stamps = load_atlas_stamps(atlas_path, glyphs)
    active_tokens = set(stamps)
    mapping = _load_json(mapping_path) if mapping_path is not None else None
    cell_size = _single_cell_size(glyphs)
    normalized_rows = [row.ljust(width) for row in rows]
    gate_mask = None
    if gate_image_path is not None:
        gate_mask = image_gate_mask(
            gate_image_path,
            width,
            height,
            mode=gate_mode,
            threshold=gate_threshold,
            dilate=gate_dilate,
        )
        if gate_mask_output_path is not None:
            write_gate_mask(gate_mask, gate_mask_output_path, scale=scale)

    image = Image.new("RGBA", (width * cell_size, height * cell_size), background)
    token_counts: Counter[str] = Counter()
    fallback_counts: Counter[str] = Counter()
    gated_blank_count = 0
    for row_index, row in enumerate(normalized_rows, start=1):
        for column_index, char in enumerate(row, start=1):
            if char == " ":
                continue
            if gate_mask is not None and not gate_mask[row_index - 1][column_index - 1]:
                gated_blank_count += 1
                continue
            token = _resolve_token(char, mapping, active_tokens)
            if token is None:
                raise ValueError(f"Unknown glyph token {char!r} at row {row_index}, column {column_index}")
            if token != char:
                fallback_counts[char] += 1
            stamp = stamps.get(token)
            if stamp is None:
                raise ValueError(f"Unknown glyph token {token!r} at row {row_index}, column {column_index}")
            image.alpha_composite(stamp, ((column_index - 1) * cell_size, (row_index - 1) * cell_size))
            token_counts[token] += 1

    if scale != 1:
        image = image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
    return {
        "input_ascii": str(ascii_path),
        "glyphs": str(glyphs_path),
        "atlas": str(atlas_path),
        "mapping": str(mapping_path) if mapping_path is not None else None,
        "output": str(output),
        "grid_width": width,
        "grid_height": height,
        "cell_size": cell_size,
        "scale": scale,
        "output_width": image.width,
        "output_height": image.height,
        "token_counts": dict(sorted(token_counts.items())),
        "fallback_counts": dict(sorted(fallback_counts.items())),
        "gate": _gate_summary(
            gate_mask,
            gate_image_path=gate_image_path,
            gate_mode=gate_mode,
            gate_threshold=gate_threshold,
            gate_dilate=gate_dilate,
            gated_blank_count=gated_blank_count,
            gate_mask_output_path=gate_mask_output_path,
        ),
    }


def image_gate_mask(
    image_path: str | Path,
    grid_width: int,
    grid_height: int,
    *,
    mode: str = "border-difference",
    threshold: int = 32,
    dilate: int = 1,
) -> list[list[bool]]:
    if mode not in GATE_MODES:
        raise ValueError(f"unknown gate mode {mode!r}; expected one of {sorted(GATE_MODES)}")
    if threshold < 0:
        raise ValueError("gate threshold must be non-negative")
    if dilate < 0:
        raise ValueError("gate dilate must be non-negative")
    if grid_width <= 0 or grid_height <= 0:
        raise ValueError("gate grid size must be positive")

    with Image.open(image_path) as source:
        image = source.convert("RGBA")
    sampled = image.resize((grid_width, grid_height), Image.Resampling.BOX)
    pixels = sampled.load()
    if mode == "alpha":
        mask = [[pixels[x, y][3] > threshold for x in range(grid_width)] for y in range(grid_height)]
    elif mode in {"black", "luminance"}:
        mask = [
            [_luminance(pixels[x, y][:3]) < threshold for x in range(grid_width)]
            for y in range(grid_height)
        ]
    else:
        background = _border_median_rgb(sampled)
        mask = [
            [_rgb_distance(pixels[x, y][:3], background) > threshold for x in range(grid_width)]
            for y in range(grid_height)
        ]
    return _dilate_mask(mask, dilate) if dilate else mask


def write_gate_mask(mask: list[list[bool]], output_path: str | Path, *, scale: int = 4) -> None:
    height = len(mask)
    width = len(mask[0]) if height else 0
    image = Image.new("L", (width, height), 0)
    pixels = image.load()
    for y, row in enumerate(mask):
        for x, value in enumerate(row):
            pixels[x, y] = 255 if value else 0
    if scale > 1:
        image = image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)


def _single_cell_size(glyphs: list[Any]) -> int:
    sizes = {glyph.cell_size for glyph in glyphs}
    if not sizes:
        return CELL_SIZE
    if len(sizes) != 1:
        raise ValueError(f"ASCII glyph rendering requires one cell size, found {sorted(sizes)}")
    return sizes.pop()


def _resolve_token(char: str, mapping: dict[str, Any] | None, active_tokens: set[str]) -> str | None:
    if char in active_tokens:
        return char
    if mapping is None:
        alias = DEFAULT_EDGE_ALIASES.get(char)
        return alias if alias in active_tokens else None
    resolved = resolve_ascii_char(char, mapping, active_tokens)
    if resolved is None:
        alias = DEFAULT_EDGE_ALIASES.get(char)
        return alias if alias in active_tokens else None
    return resolved["token"]


def _load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _luminance(rgb: tuple[int, int, int]) -> int:
    red, green, blue = rgb
    return int(round(0.299 * red + 0.587 * green + 0.114 * blue))


def _rgb_distance(left: tuple[int, int, int], right: tuple[int, int, int]) -> float:
    return sum((int(a) - int(b)) ** 2 for a, b in zip(left, right)) ** 0.5


def _border_median_rgb(image: Image.Image) -> tuple[int, int, int]:
    pixels = image.load()
    samples: list[tuple[int, int, int]] = []
    for x in range(image.width):
        samples.append(pixels[x, 0][:3])
        samples.append(pixels[x, image.height - 1][:3])
    for y in range(image.height):
        samples.append(pixels[0, y][:3])
        samples.append(pixels[image.width - 1, y][:3])
    return tuple(_median([sample[channel] for sample in samples]) for channel in range(3))


def _median(values: list[int]) -> int:
    ordered = sorted(values)
    return int(ordered[len(ordered) // 2])


def _dilate_mask(mask: list[list[bool]], radius: int) -> list[list[bool]]:
    if not mask or not mask[0]:
        return mask
    height = len(mask)
    width = len(mask[0])
    result = [[False for _ in range(width)] for _ in range(height)]
    for y, row in enumerate(mask):
        for x, value in enumerate(row):
            if not value:
                continue
            for yy in range(max(0, y - radius), min(height, y + radius + 1)):
                for xx in range(max(0, x - radius), min(width, x + radius + 1)):
                    result[yy][xx] = True
    return result


def _gate_summary(
    gate_mask: list[list[bool]] | None,
    *,
    gate_image_path: str | Path | None,
    gate_mode: str,
    gate_threshold: int,
    gate_dilate: int,
    gated_blank_count: int,
    gate_mask_output_path: str | Path | None,
) -> dict[str, Any] | None:
    if gate_mask is None:
        return None
    kept = sum(1 for row in gate_mask for value in row if value)
    total = sum(len(row) for row in gate_mask)
    return {
        "image": str(gate_image_path),
        "mode": gate_mode,
        "threshold": gate_threshold,
        "dilate": gate_dilate,
        "kept_cells": kept,
        "blank_cells": total - kept,
        "gated_token_cells": gated_blank_count,
        "mask_output": str(gate_mask_output_path) if gate_mask_output_path is not None else None,
    }
