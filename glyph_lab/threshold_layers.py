from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from PIL import Image, ImageDraw

from .ascii_bridge import resolve_ascii_char
from .ascii_glyph_renderer import _luminance, _median, _tint_stamp
from .atlas import load_atlas_stamps
from .foreground_mask import foreground_mask, mask_and, write_foreground_mask
from .schema import load_glyphs


DEFAULT_THRESHOLDS = (16, 24, 32, 40, 48, 56)


def render_threshold_color_layers(
    image_path: str | Path,
    glyphs_path: str | Path,
    atlas_path: str | Path,
    output_dir: str | Path,
    *,
    thresholds: list[int] | tuple[int, ...] = DEFAULT_THRESHOLDS,
    grid_width: int = 128,
    grid_height: int = 128,
    fill_token: str = "#",
    mapping_path: str | Path | None = None,
    foreground_mode: str = "auto",
    foreground_alpha_threshold: int = 1,
    foreground_background_threshold: int = 28,
    scale: int = 2,
) -> dict[str, Any]:
    thresholds = parse_thresholds(thresholds)
    if grid_width <= 0 or grid_height <= 0:
        raise ValueError("grid width and height must be positive")
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
        raise ValueError(f"unknown threshold fill token {fill_token!r}")
    stamp = stamps[token]
    cell_size = stamp.width

    with Image.open(image_path) as source:
        source_image = source.convert("RGBA")
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

    previous_mask = _empty_mask(grid_width, grid_height)
    layers = []
    stack = Image.new("RGBA", (grid_width * cell_size, grid_height * cell_size), (255, 255, 255, 255))
    for threshold in thresholds:
        cumulative_mask = mask_and(_threshold_mask(source_image, grid_width, grid_height, threshold), foreground)
        delta_mask = _subtract_mask(cumulative_mask, previous_mask)
        cumulative_count = _mask_count(cumulative_mask)
        delta_count = _mask_count(delta_mask)
        lower = _previous_threshold(thresholds, threshold)

        cumulative_mask_path = masks_dir / f"t{threshold}_cumulative_mask.png"
        delta_mask_path = masks_dir / f"t{threshold}_delta_mask.png"
        black_path = black_dir / f"t{threshold}_delta_black.png"
        color_path = color_dir / f"t{threshold}_delta_color.png"
        _write_mask(cumulative_mask, cumulative_mask_path, scale=scale)
        _write_mask(delta_mask, delta_mask_path, scale=scale)

        black_image = _render_mask_layer(delta_mask, stamp, (0, 0, 0))
        color_image = _render_threshold_sampled_layer(source_image, delta_mask, stamp, threshold, lower)
        stack.alpha_composite(color_image)

        _save_scaled(black_image, black_path, scale)
        _save_scaled(color_image, color_path, scale)
        layers.append(
            {
                "threshold": threshold,
                "lower_threshold": lower,
                "luminance_range": [max(0, lower), threshold - 1],
                "cumulative_cells": cumulative_count,
                "delta_cells": delta_count,
                "cumulative_mask": str(cumulative_mask_path),
                "delta_mask": str(delta_mask_path),
                "black_layer": str(black_path),
                "colorized_layer": str(color_path),
            }
        )
        previous_mask = cumulative_mask

    stacked_path = composites_dir / "stacked_delta_color.png"
    _save_scaled(stack, stacked_path, scale)
    contact_sheet_path = output / "threshold_color_layers_contact_sheet.png"
    _write_contact_sheet(image_path, layers, stacked_path, contact_sheet_path)

    manifest = {
        "source_image": str(image_path),
        "glyphs": str(glyphs_path),
        "atlas": str(atlas_path),
        "mapping": str(mapping_path) if mapping_path is not None else None,
        "grid_width": grid_width,
        "grid_height": grid_height,
        "thresholds": thresholds,
        "fill_token": fill_token,
        "resolved_token": token,
        "ink_mode": "threshold-sampled-delta",
        "foreground": {**foreground_summary, "mask": str(foreground_mask_path)},
        "rule": "foreground mask is applied first; each delta t-layer samples median source RGB from foreground pixels inside the same cell whose luminance is in that threshold band",
        "layers": layers,
        "stacked": str(stacked_path),
        "contact_sheet": str(contact_sheet_path),
    }
    _write_json(output / "manifest.json", manifest)
    return manifest


def parse_thresholds(value: str | list[int] | tuple[int, ...]) -> list[int]:
    if isinstance(value, str):
        parts = [part.strip() for part in value.split(",") if part.strip()]
        if not parts:
            raise ValueError("thresholds must contain at least one value")
        try:
            thresholds = [int(part) for part in parts]
        except ValueError as exc:
            raise ValueError(f"thresholds must be comma-separated integers, got {value!r}") from exc
    else:
        thresholds = [int(part) for part in value]
    if not thresholds:
        raise ValueError("thresholds must contain at least one value")
    if any(threshold < 0 or threshold > 255 for threshold in thresholds):
        raise ValueError("thresholds must be between 0 and 255")
    if thresholds != sorted(set(thresholds)):
        raise ValueError("thresholds must be unique and sorted ascending")
    return thresholds


def _threshold_mask(image: Image.Image, grid_width: int, grid_height: int, threshold: int) -> list[list[bool]]:
    sampled = image.resize((grid_width, grid_height), Image.Resampling.BOX)
    pixels = sampled.load()
    return [
        [_luminance(pixels[x, y][:3]) < threshold for x in range(grid_width)]
        for y in range(grid_height)
    ]


def _render_threshold_sampled_layer(
    image: Image.Image,
    mask: list[list[bool]],
    stamp: Image.Image,
    threshold: int,
    lower_threshold: int,
) -> Image.Image:
    grid_height = len(mask)
    grid_width = len(mask[0]) if grid_height else 0
    output = Image.new("RGBA", (grid_width * stamp.width, grid_height * stamp.height), (255, 255, 255, 0))
    for y, row in enumerate(mask):
        y0, y1 = _source_span(y, grid_height, image.height)
        for x, keep in enumerate(row):
            if not keep:
                continue
            x0, x1 = _source_span(x, grid_width, image.width)
            rgb = _sample_band_rgb(image, x0, y0, x1, y1, lower_threshold, threshold)
            output.alpha_composite(_tint_stamp(stamp, rgb), (x * stamp.width, y * stamp.height))
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


def _sample_band_rgb(
    image: Image.Image,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    lower_threshold: int,
    threshold: int,
) -> tuple[int, int, int]:
    pixels = image.load()
    candidates = []
    fallback = []
    for y in range(y0, y1):
        for x in range(x0, x1):
            red, green, blue, alpha = pixels[x, y]
            if alpha == 0:
                continue
            rgb = (red, green, blue)
            luminance = _luminance(rgb)
            if lower_threshold <= luminance < threshold:
                candidates.append(rgb)
            elif luminance < threshold:
                fallback.append(rgb)
    colors = candidates or fallback
    if colors:
        return tuple(_median([color[channel] for color in colors]) for channel in range(3))
    crop = image.crop((x0, y0, x1, y1)).resize((1, 1), Image.Resampling.BOX)
    return crop.getpixel((0, 0))[:3]


def _source_span(index: int, grid_size: int, source_size: int) -> tuple[int, int]:
    start = int(index * source_size / grid_size)
    end = int((index + 1) * source_size / grid_size)
    if end <= start:
        end = start + 1
    return max(0, start), min(source_size, end)


def _empty_mask(width: int, height: int) -> list[list[bool]]:
    return [[False for _ in range(width)] for _ in range(height)]


def _subtract_mask(current: list[list[bool]], previous: list[list[bool]]) -> list[list[bool]]:
    return [
        [value and not previous[y][x] for x, value in enumerate(row)]
        for y, row in enumerate(current)
    ]


def _mask_count(mask: list[list[bool]]) -> int:
    return sum(1 for row in mask for value in row if value)


def _previous_threshold(thresholds: list[int], threshold: int) -> int:
    index = thresholds.index(threshold)
    return -1 if index == 0 else thresholds[index - 1]


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


def _write_contact_sheet(
    image_path: str | Path,
    layers: list[dict[str, Any]],
    stacked_path: str | Path,
    output_path: str | Path,
) -> None:
    thumb = 220
    pad = 12
    label_h = 34
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
        paste_cell(0, 1, "stacked", stacked.convert("RGB"), "delta color")
    paste_cell(0, 2, "rule", Image.new("RGB", (thumb, thumb), "white"), "t-band mask -> source color")

    for index, layer in enumerate(layers, start=1):
        threshold = layer["threshold"]
        subtitle = f"{layer['delta_cells']} delta cells"
        with Image.open(layer["delta_mask"]) as mask:
            paste_cell(index, 0, f"delta mask t{threshold}", mask.convert("RGB"), subtitle)
        with Image.open(layer["black_layer"]) as black:
            paste_cell(index, 1, f"black t{threshold}", black.convert("RGB"))
        with Image.open(layer["colorized_layer"]) as color:
            paste_cell(index, 2, f"color t{threshold}", color.convert("RGB"))

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


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
