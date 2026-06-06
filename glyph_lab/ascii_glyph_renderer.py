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
GATE_MODES = {"alpha", "black", "luminance", "border-difference", "sample-colors"}
INK_MODES = {"atlas", "solid", "sampled", "sampled-local"}


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
    gate_samples_path: str | Path | None = None,
    gate_samples_key: str = "eyedropper_samples",
    gate_include_boxes: list[tuple[int, int, int, int]] | None = None,
    gate_fill_token: str | None = None,
    ink_mode: str = "atlas",
    ink_color: str | None = None,
    ink_sample_radius: int = 6,
    ink_ignore_luminance: int = 40,
    ink_palette_threshold: int | None = None,
    scale: int = 4,
    background: tuple[int, int, int, int] = (255, 255, 255, 255),
) -> dict[str, Any]:
    if scale < 1:
        raise ValueError("scale must be at least 1")
    if ink_mode not in INK_MODES:
        raise ValueError(f"unknown ink mode {ink_mode!r}; expected one of {sorted(INK_MODES)}")
    if ink_sample_radius < 0:
        raise ValueError("ink sample radius must be non-negative")
    if not 0 <= ink_ignore_luminance <= 255:
        raise ValueError("ink ignore luminance must be between 0 and 255")
    if ink_palette_threshold is not None and ink_palette_threshold < 0:
        raise ValueError("ink palette threshold must be non-negative")

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
    gate_fill_resolved = None
    solid_ink_color = _parse_hex_rgb(ink_color) if ink_mode == "solid" else None
    if ink_mode == "solid" and solid_ink_color is None:
        raise ValueError("solid ink mode requires --ink-color")
    gate_sample_colors = _load_sample_colors(gate_samples_path, gate_samples_key) if gate_samples_path else None
    if ink_mode in {"sampled", "sampled-local"} and gate_image_path is None:
        raise ValueError(f"{ink_mode} ink mode requires --gate-image")
    sampled_ink_colors = None
    if ink_mode == "sampled":
        sampled_ink_colors = _sample_rgb_grid(gate_image_path, width, height)
    elif ink_mode == "sampled-local":
        sampled_ink_colors = _sample_local_rgb_grid(
            gate_image_path,
            width,
            height,
            radius=ink_sample_radius,
            ignore_luminance=ink_ignore_luminance,
            palette_colors=gate_sample_colors if ink_palette_threshold is not None else None,
            palette_threshold=ink_palette_threshold,
        )
    if gate_image_path is not None:
        gate_mask = image_gate_mask(
            gate_image_path,
            width,
            height,
            mode=gate_mode,
            threshold=gate_threshold,
            dilate=gate_dilate,
            sample_colors=gate_sample_colors,
            include_boxes=gate_include_boxes,
        )
        if gate_mask_output_path is not None:
            write_gate_mask(gate_mask, gate_mask_output_path, scale=scale)
    if gate_fill_token is not None:
        if gate_mask is None:
            raise ValueError("gate fill token requires --gate-image")
        gate_fill_resolved = _resolve_token(gate_fill_token, mapping, active_tokens)
        if gate_fill_resolved is None:
            raise ValueError(f"Unknown gate fill token {gate_fill_token!r}")

    image = Image.new("RGBA", (width * cell_size, height * cell_size), background)
    token_counts: Counter[str] = Counter()
    fallback_counts: Counter[str] = Counter()
    gated_blank_count = 0
    gate_filled_count = 0
    for row_index, row in enumerate(normalized_rows, start=1):
        for column_index, char in enumerate(row, start=1):
            gate_kept = gate_mask[row_index - 1][column_index - 1] if gate_mask is not None else True
            if not gate_kept:
                if char != " ":
                    gated_blank_count += 1
                continue
            if gate_fill_resolved is not None:
                token = gate_fill_resolved
                gate_filled_count += 1
            else:
                if char == " ":
                    continue
                token = _resolve_token(char, mapping, active_tokens)
            if token is None:
                raise ValueError(f"Unknown glyph token {char!r} at row {row_index}, column {column_index}")
            if char != " " and token != char:
                fallback_counts[char] += 1
            stamp = stamps.get(token)
            if stamp is None:
                raise ValueError(f"Unknown glyph token {token!r} at row {row_index}, column {column_index}")
            ink_rgb = _ink_rgb(
                ink_mode,
                solid_ink_color=solid_ink_color,
                sampled_ink_colors=sampled_ink_colors,
                row_index=row_index,
                column_index=column_index,
            )
            draw_stamp = _tint_stamp(stamp, ink_rgb) if ink_rgb is not None else stamp
            image.alpha_composite(draw_stamp, ((column_index - 1) * cell_size, (row_index - 1) * cell_size))
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
        "ink": {
            "mode": ink_mode,
            "color": ink_color,
            "source": str(gate_image_path) if ink_mode in {"sampled", "sampled-local"} else None,
            "sample_radius": ink_sample_radius if ink_mode == "sampled-local" else None,
            "ignore_luminance": ink_ignore_luminance if ink_mode == "sampled-local" else None,
            "palette_threshold": ink_palette_threshold if ink_mode == "sampled-local" else None,
        },
        "gate": _gate_summary(
            gate_mask,
            gate_image_path=gate_image_path,
            gate_mode=gate_mode,
            gate_threshold=gate_threshold,
            gate_dilate=gate_dilate,
            gated_blank_count=gated_blank_count,
            gate_mask_output_path=gate_mask_output_path,
            gate_samples_path=gate_samples_path,
            gate_sample_count=len(gate_sample_colors or []),
            gate_include_boxes=gate_include_boxes,
            gate_fill_token=gate_fill_token,
            gate_filled_count=gate_filled_count,
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
    sample_colors: list[tuple[int, int, int]] | None = None,
    include_boxes: list[tuple[int, int, int, int]] | None = None,
) -> list[list[bool]]:
    if mode not in GATE_MODES:
        raise ValueError(f"unknown gate mode {mode!r}; expected one of {sorted(GATE_MODES)}")
    if threshold < 0:
        raise ValueError("gate threshold must be non-negative")
    if dilate < 0:
        raise ValueError("gate dilate must be non-negative")
    if grid_width <= 0 or grid_height <= 0:
        raise ValueError("gate grid size must be positive")
    include_boxes = _validate_include_boxes(include_boxes)

    with Image.open(image_path) as source:
        image = source.convert("RGBA")
    source_width, source_height = image.size
    sampled = image.resize((grid_width, grid_height), Image.Resampling.BOX)
    pixels = sampled.load()
    if mode == "alpha":
        mask = [[pixels[x, y][3] > threshold for x in range(grid_width)] for y in range(grid_height)]
    elif mode in {"black", "luminance"}:
        mask = [
            [_luminance(pixels[x, y][:3]) < threshold for x in range(grid_width)]
            for y in range(grid_height)
        ]
    elif mode == "sample-colors":
        if not sample_colors:
            raise ValueError("sample-colors gate mode requires at least one eyedropper sample color")
        mask = [
            [
                min(_rgb_distance(pixels[x, y][:3], sample) for sample in sample_colors) <= threshold
                for x in range(grid_width)
            ]
            for y in range(grid_height)
        ]
    else:
        background = _border_median_rgb(sampled)
        mask = [
            [_rgb_distance(pixels[x, y][:3], background) > threshold for x in range(grid_width)]
            for y in range(grid_height)
        ]
    if include_boxes:
        mask = _apply_include_boxes(mask, include_boxes, source_width, source_height)
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


def _load_sample_colors(path: str | Path, key: str) -> list[tuple[int, int, int]]:
    payload = _load_json(path)
    sample_payload = payload.get(key)
    if sample_payload is None:
        raise ValueError(f"sample color JSON does not contain key {key!r}")
    samples = sample_payload.get("samples") if isinstance(sample_payload, dict) else None
    if not isinstance(samples, list) or not samples:
        raise ValueError(f"sample color JSON key {key!r} must contain a non-empty samples list")

    colors = []
    for index, sample in enumerate(samples):
        rgba = sample.get("rgba") if isinstance(sample, dict) else None
        if not isinstance(rgba, list) or len(rgba) < 3:
            raise ValueError(f"sample color at index {index} is missing rgba")
        colors.append((int(rgba[0]), int(rgba[1]), int(rgba[2])))
    return colors


def _validate_include_boxes(
    boxes: list[tuple[int, int, int, int]] | None,
) -> list[tuple[int, int, int, int]]:
    if not boxes:
        return []
    for box in boxes:
        x0, y0, x1, y1 = box
        if x0 < 0 or y0 < 0 or x1 <= x0 or y1 <= y0:
            raise ValueError(f"gate include box must be x0,y0,x1,y1 with positive size, got {box!r}")
    return boxes


def _apply_include_boxes(
    mask: list[list[bool]],
    boxes: list[tuple[int, int, int, int]],
    source_width: int,
    source_height: int,
) -> list[list[bool]]:
    height = len(mask)
    width = len(mask[0]) if height else 0
    filtered = [[False for _ in range(width)] for _ in range(height)]
    for y, row in enumerate(mask):
        source_y = min(source_height - 1, int((y + 0.5) * source_height / height))
        for x, value in enumerate(row):
            if not value:
                continue
            source_x = min(source_width - 1, int((x + 0.5) * source_width / width))
            if any(x0 <= source_x < x1 and y0 <= source_y < y1 for x0, y0, x1, y1 in boxes):
                filtered[y][x] = True
    return filtered


def _sample_rgb_grid(image_path: str | Path | None, grid_width: int, grid_height: int) -> list[list[tuple[int, int, int]]]:
    if image_path is None:
        raise ValueError("sampled ink mode requires --gate-image")
    with Image.open(image_path) as source:
        sampled = source.convert("RGBA").resize((grid_width, grid_height), Image.Resampling.BOX)
    pixels = sampled.load()
    return [[pixels[x, y][:3] for x in range(grid_width)] for y in range(grid_height)]


def _sample_local_rgb_grid(
    image_path: str | Path | None,
    grid_width: int,
    grid_height: int,
    *,
    radius: int,
    ignore_luminance: int,
    palette_colors: list[tuple[int, int, int]] | None = None,
    palette_threshold: int | None = None,
) -> list[list[tuple[int, int, int]]]:
    if image_path is None:
        raise ValueError("sampled-local ink mode requires --gate-image")
    with Image.open(image_path) as source:
        image = source.convert("RGBA")
    pixels = image.load()
    exact = image.resize((grid_width, grid_height), Image.Resampling.BOX).load()
    rows = []
    for grid_y in range(grid_height):
        row = []
        source_y = min(image.height - 1, int((grid_y + 0.5) * image.height / grid_height))
        for grid_x in range(grid_width):
            source_x = min(image.width - 1, int((grid_x + 0.5) * image.width / grid_width))
            candidates = _local_color_candidates(
                pixels,
                image.width,
                image.height,
                source_x,
                source_y,
                radius,
                ignore_luminance,
                palette_colors,
                palette_threshold,
            )
            if not candidates and palette_threshold is None:
                candidates = _local_color_candidates(
                    pixels,
                    image.width,
                    image.height,
                    source_x,
                    source_y,
                    radius,
                    ignore_luminance,
                    None,
                    None,
                )
            row.append(_average_rgb(candidates) if candidates else exact[grid_x, grid_y][:3])
        rows.append(row)
    return rows


def _local_color_candidates(
    pixels: Any,
    width: int,
    height: int,
    source_x: int,
    source_y: int,
    radius: int,
    ignore_luminance: int,
    palette_colors: list[tuple[int, int, int]] | None,
    palette_threshold: int | None,
) -> list[tuple[int, int, int]]:
    candidates = []
    for y in range(max(0, source_y - radius), min(height, source_y + radius + 1)):
        for x in range(max(0, source_x - radius), min(width, source_x + radius + 1)):
            red, green, blue, alpha = pixels[x, y]
            if alpha == 0:
                continue
            rgb = (red, green, blue)
            if _luminance(rgb) <= ignore_luminance:
                continue
            if palette_colors is not None and palette_threshold is not None:
                if min(_rgb_distance(rgb, palette) for palette in palette_colors) > palette_threshold:
                    continue
            candidates.append(rgb)
    return candidates


def _average_rgb(colors: list[tuple[int, int, int]]) -> tuple[int, int, int]:
    return tuple(int(round(sum(color[channel] for color in colors) / len(colors))) for channel in range(3))


def _ink_rgb(
    ink_mode: str,
    *,
    solid_ink_color: tuple[int, int, int] | None,
    sampled_ink_colors: list[list[tuple[int, int, int]]] | None,
    row_index: int,
    column_index: int,
) -> tuple[int, int, int] | None:
    if ink_mode == "solid":
        return solid_ink_color
    if ink_mode in {"sampled", "sampled-local"}:
        if sampled_ink_colors is None:
            raise ValueError("sampled ink mode requires sampled colors")
        return sampled_ink_colors[row_index - 1][column_index - 1]
    return None


def _tint_stamp(stamp: Image.Image, rgb: tuple[int, int, int]) -> Image.Image:
    rgba = stamp.convert("RGBA")
    _, _, _, alpha = rgba.split()
    tinted = Image.new("RGBA", rgba.size, (*rgb, 0))
    tinted.putalpha(alpha)
    return tinted


def _parse_hex_rgb(value: str | None) -> tuple[int, int, int] | None:
    if value is None:
        return None
    text = value.strip()
    if text.startswith("#"):
        text = text[1:]
    if len(text) != 6:
        raise ValueError(f"ink color must be #RRGGBB, got {value!r}")
    try:
        return tuple(int(text[index : index + 2], 16) for index in (0, 2, 4))
    except ValueError as exc:
        raise ValueError(f"ink color must be #RRGGBB, got {value!r}") from exc


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
    gate_samples_path: str | Path | None,
    gate_sample_count: int,
    gate_include_boxes: list[tuple[int, int, int, int]] | None,
    gate_fill_token: str | None,
    gate_filled_count: int,
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
        "samples": str(gate_samples_path) if gate_samples_path is not None else None,
        "sample_count": gate_sample_count,
        "include_boxes": [list(box) for box in gate_include_boxes or []],
        "fill_token": gate_fill_token,
        "filled_cells": gate_filled_count,
        "kept_cells": kept,
        "blank_cells": total - kept,
        "gated_token_cells": gated_blank_count,
        "mask_output": str(gate_mask_output_path) if gate_mask_output_path is not None else None,
    }
