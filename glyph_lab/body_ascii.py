from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from PIL import Image, ImageDraw, ImageFont

from .ascii_glyph_renderer import render_ascii_glyphs


DEFAULT_SHADE_RAMP = ".*,qpbdxChs^_[]:S;#"
PALETTE_THEMES = {
    "source": None,
    "maroon": (
        (42, 6, 16),
        (74, 11, 24),
        (110, 16, 34),
        (140, 29, 45),
        (168, 50, 62),
        (197, 83, 90),
        (223, 133, 128),
        (241, 187, 176),
    ),
}


def render_body_ascii_proof(
    mannequin_path: str | Path,
    output_path: str | Path,
    *,
    glyphs_path: str | Path,
    atlas_path: str | Path,
    mapping_path: str | Path | None = None,
    shade_ramp_path: str | Path | None = None,
    grid_width: int = 128,
    grid_height: int = 192,
    palette_size: int = 8,
    palette_theme: str = "source",
    min_cell_coverage: float = 0.05,
    scale: int = 2,
) -> dict[str, Any]:
    if grid_width <= 0 or grid_height <= 0:
        raise ValueError("grid width and height must be positive")
    if palette_size < 1:
        raise ValueError("palette size must be at least 1")
    if not 0.0 < min_cell_coverage <= 1.0:
        raise ValueError("min cell coverage must be greater than 0 and at most 1")
    if scale < 1:
        raise ValueError("scale must be at least 1")
    if palette_theme not in PALETTE_THEMES:
        raise ValueError(f"unknown palette theme {palette_theme!r}; expected one of {sorted(PALETTE_THEMES)}")

    output = Path(output_path)
    output.mkdir(parents=True, exist_ok=True)
    recipe_path = Path(mannequin_path)
    recipe = _load_json(recipe_path)
    width = int(recipe.get("grid", {}).get("width", 0))
    height = int(recipe.get("grid", {}).get("height", 0))
    if width <= 0 or height <= 0:
        raise ValueError("mannequin recipe must include positive grid width and height")

    parts = _load_cutout_parts(recipe.get("parts", []), recipe_path.parent, width, height)
    if not parts:
        raise ValueError("mannequin recipe has no shaded cutouts to render")

    shade_ramp = _load_shade_ramp(shade_ramp_path)
    shaded_source = _render_shaded_source(width, height, parts)
    ink_source = _recolor_by_luminance(shaded_source, PALETTE_THEMES[palette_theme]) if palette_theme != "source" else shaded_source
    ascii_rows, ascii_summary = _image_to_ascii_rows(
        shaded_source,
        shade_ramp,
        grid_width,
        grid_height,
        min_cell_coverage=min_cell_coverage,
    )

    shaded_source_path = output / "body_shaded_source.png"
    ink_source_path = output / "body_ink_source.png"
    ascii_path = output / "body_ascii.txt"
    ascii_palette_path = output / "body_ascii_palette.txt"
    proof_path = output / "body_ascii_glyph_proof.png"
    solid_proof_path = output / "body_ascii_solid_proof.png"
    contact_sheet_path = output / "body_ascii_contact_sheet.png"
    palette_json_path = output / "body_palette.json"
    manifest_path = output / "body_ascii_manifest.json"

    shaded_source.save(shaded_source_path)
    ink_source.save(ink_source_path)
    ascii_path.write_text("\n".join(ascii_rows) + "\n", encoding="utf-8")
    ascii_palette_path.write_text(shade_ramp + "\n", encoding="utf-8")

    render_result = render_ascii_glyphs(
        ascii_path,
        glyphs_path,
        atlas_path,
        proof_path,
        mapping_path=mapping_path,
        gate_image_path=ink_source_path,
        gate_mode="alpha",
        gate_threshold=1,
        gate_dilate=0,
        gate_mask_output_path=output / "body_gate_mask.png",
        ink_mode="threshold-sampled",
        ink_palette_size=palette_size,
        scale=scale,
    )
    solid_render_result = render_ascii_glyphs(
        ascii_path,
        glyphs_path,
        atlas_path,
        solid_proof_path,
        mapping_path=mapping_path,
        gate_image_path=ink_source_path,
        gate_mode="alpha",
        gate_threshold=1,
        gate_dilate=0,
        gate_fill_token="#",
        ink_mode="threshold-sampled",
        ink_palette_size=palette_size,
        scale=scale,
    )
    reduced_palette = render_result.get("ink", {}).get("reduced_palette", [])
    palette_payload = {
        "schema": "glyph_lab.body_palette.v0",
        "source_image": str(ink_source_path),
        "palette_theme": palette_theme,
        "palette_size_requested": palette_size,
        "palette": reduced_palette,
        "rule": "palette is reduced from shaded mannequin cutouts, not from region-id colors",
    }
    _write_json(palette_json_path, palette_payload)

    _write_contact_sheet(
        [
            ("shaded source", shaded_source),
            ("ink source", ink_source),
            ("tonal glyph proof", Image.open(proof_path).convert("RGBA")),
            ("solid cell proof", Image.open(solid_proof_path).convert("RGBA")),
        ],
        contact_sheet_path,
    )

    manifest = {
        "schema": "glyph_lab.body_ascii_proof.v0",
        "source_mannequin": str(recipe_path),
        "grid": {"width": grid_width, "height": grid_height},
        "shade_ramp": shade_ramp,
        "palette_theme": palette_theme,
        "min_cell_coverage": min_cell_coverage,
        "occupied_cells": ascii_summary["occupied_cells"],
        "luminance_range": ascii_summary["luminance_range"],
        "glyphs": str(glyphs_path),
        "atlas": str(atlas_path),
        "mapping": str(mapping_path) if mapping_path is not None else None,
        "render_result": render_result,
        "solid_render_result": solid_render_result,
        "outputs": {
            "shaded_source": str(shaded_source_path),
            "ink_source": str(ink_source_path),
            "ascii": str(ascii_path),
            "ascii_palette": str(ascii_palette_path),
            "palette": str(palette_json_path),
            "glyph_proof": str(proof_path),
            "solid_proof": str(solid_proof_path),
            "contact_sheet": str(contact_sheet_path),
            "manifest": str(manifest_path),
        },
        "rule": "ASCII cells carry tonal body shape; glyph ink is sampled from a reduced mannequin palette",
    }
    _write_json(manifest_path, manifest)
    return manifest


def _load_cutout_parts(parts: list[dict[str, Any]], root: Path, width: int, height: int) -> list[dict[str, Any]]:
    loaded = []
    for part in sorted(parts, key=lambda item: int(item.get("draw_order", 0))):
        cutout_path = _resolve_path(root, part.get("cutout"))
        if cutout_path is None or not cutout_path.exists():
            continue
        image = Image.open(cutout_path).convert("RGBA")
        if image.size != (width, height):
            image = image.resize((width, height), Image.Resampling.NEAREST)
        loaded.append({**part, "_cutout": image})
    return loaded


def _render_shaded_source(width: int, height: int, parts: list[dict[str, Any]]) -> Image.Image:
    image = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    for part in parts:
        image.alpha_composite(part["_cutout"])
    return image


def _image_to_ascii_rows(
    image: Image.Image,
    shade_ramp: str,
    grid_width: int,
    grid_height: int,
    *,
    min_cell_coverage: float,
) -> tuple[list[str], dict[str, Any]]:
    pixels = image.load()
    cells: list[list[dict[str, Any]]] = []
    luminances = []
    occupied_cells = 0
    for row in range(grid_height):
        cell_row = []
        y0, y1 = _span(row, grid_height, image.height)
        for column in range(grid_width):
            x0, x1 = _span(column, grid_width, image.width)
            alpha_count = 0
            luminance_total = 0.0
            for y in range(y0, y1):
                for x in range(x0, x1):
                    red, green, blue, alpha = pixels[x, y]
                    if alpha:
                        alpha_count += 1
                        luminance_total += _luminance((red, green, blue))
            total = max(1, (x1 - x0) * (y1 - y0))
            coverage = alpha_count / total
            if coverage < min_cell_coverage or alpha_count == 0:
                cell_row.append({"char": " ", "coverage": coverage, "luminance": None})
                continue
            luminance = luminance_total / alpha_count
            luminances.append(luminance)
            occupied_cells += 1
            cell_row.append({"char": None, "coverage": coverage, "luminance": luminance})
        cells.append(cell_row)

    if not luminances:
        return [" " * grid_width for _ in range(grid_height)], {"occupied_cells": 0, "luminance_range": None}

    low = min(luminances)
    high = max(luminances)
    rows = []
    for cell_row in cells:
        chars = []
        for cell in cell_row:
            if cell["luminance"] is None:
                chars.append(" ")
            else:
                chars.append(_shade_char(float(cell["luminance"]), shade_ramp, low, high))
        rows.append("".join(chars))
    return rows, {
        "occupied_cells": occupied_cells,
        "luminance_range": [round(low, 2), round(high, 2)],
    }


def _recolor_by_luminance(image: Image.Image, palette: tuple[tuple[int, int, int], ...] | None) -> Image.Image:
    if palette is None:
        return image
    luminances = []
    source = image.convert("RGBA")
    pixels = source.load()
    for y in range(source.height):
        for x in range(source.width):
            red, green, blue, alpha = pixels[x, y]
            if alpha:
                luminances.append(_luminance((red, green, blue)))
    if not luminances:
        return source
    low = min(luminances)
    high = max(luminances)
    output = Image.new("RGBA", source.size, (255, 255, 255, 0))
    target = output.load()
    for y in range(source.height):
        for x in range(source.width):
            red, green, blue, alpha = pixels[x, y]
            if not alpha:
                continue
            luminance = _luminance((red, green, blue))
            color = _palette_color(luminance, palette, low, high)
            target[x, y] = (*color, alpha)
    return output


def _palette_color(
    luminance: float,
    palette: tuple[tuple[int, int, int], ...],
    low: float,
    high: float,
) -> tuple[int, int, int]:
    if len(palette) == 1 or high <= low:
        return palette[-1]
    normalized_lightness = (luminance - low) / (high - low)
    index = int(round(normalized_lightness * (len(palette) - 1)))
    return palette[max(0, min(len(palette) - 1, index))]


def _shade_char(luminance: float, shade_ramp: str, low: float, high: float) -> str:
    if len(shade_ramp) == 1 or high <= low:
        return shade_ramp[-1]
    normalized_darkness = 1.0 - ((luminance - low) / (high - low))
    index = int(round(normalized_darkness * (len(shade_ramp) - 1)))
    return shade_ramp[max(0, min(len(shade_ramp) - 1, index))]


def _span(index: int, grid_size: int, source_size: int) -> tuple[int, int]:
    start = int(index * source_size / grid_size)
    end = int((index + 1) * source_size / grid_size)
    if end <= start:
        end = start + 1
    return max(0, start), min(source_size, end)


def _load_shade_ramp(path: str | Path | None) -> str:
    if path is None:
        return DEFAULT_SHADE_RAMP
    ramp = Path(path).read_text(encoding="utf-8").strip("\n")
    if not ramp:
        raise ValueError("shade ramp must not be empty")
    if " " in ramp:
        raise ValueError("shade ramp must not contain spaces; spaces are reserved for empty cells")
    return ramp


def _write_contact_sheet(items: list[tuple[str, Image.Image]], output_path: Path) -> None:
    label_height = 18
    padding = 12
    cell_width = max(image.width for _, image in items)
    cell_height = max(image.height for _, image in items) + label_height
    sheet = Image.new(
        "RGBA",
        (padding + len(items) * (cell_width + padding), padding + cell_height + padding),
        (245, 245, 245, 255),
    )
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    x = padding
    for name, image in items:
        draw.text((x, padding), name, fill=(0, 0, 0), font=font)
        sheet.alpha_composite(image, (x, padding + label_height))
        x += cell_width + padding
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path)


def _resolve_path(root: Path, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else root / path


def _luminance(rgb: tuple[int, int, int]) -> float:
    red, green, blue = rgb
    return 0.299 * red + 0.587 * green + 0.114 * blue


def _load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
