from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from PIL import Image, ImageDraw, ImageFont


DEFAULT_PART_MATERIALS = {
    "head": "skin",
    "neck": "skin",
    "torso": "blue",
    "pelvis": "brown",
    "upper_arm_left": "skin",
    "lower_arm_left": "skin",
    "hand_left": "brown",
    "upper_arm_right": "skin",
    "lower_arm_right": "skin",
    "hand_right": "brown",
    "upper_leg_left": "gray",
    "lower_leg_left": "brown",
    "foot_left": "brown",
    "upper_leg_right": "gray",
    "lower_leg_right": "brown",
    "foot_right": "brown",
}


def recolor_mannequin_from_reference(
    mannequin_path: str | Path,
    style_recipe_path: str | Path,
    output_path: str | Path,
    *,
    sprite_parts_path: str | Path | None = None,
    outline_threshold: int = 72,
) -> dict[str, Any]:
    if not 0 <= outline_threshold <= 255:
        raise ValueError("outline threshold must be between 0 and 255")
    recipe_path = Path(mannequin_path)
    style_path = Path(style_recipe_path)
    recipe = _load_json(recipe_path)
    style = _load_json(style_path)
    sprite_parts = _load_json(sprite_parts_path) if sprite_parts_path is not None else None
    width = int(recipe.get("grid", {}).get("width", 0))
    height = int(recipe.get("grid", {}).get("height", 0))
    if width <= 0 or height <= 0:
        raise ValueError("mannequin recipe must include positive grid width and height")

    palettes = _style_palettes(style)
    if "outline" not in palettes and "dark" not in palettes:
        raise ValueError("reference style recipe must include outline or dark palette")
    missing = sorted({material for material in DEFAULT_PART_MATERIALS.values() if material not in palettes})
    if missing:
        raise ValueError(f"reference style recipe is missing required palettes: {missing}")

    output = Path(output_path)
    output.mkdir(parents=True, exist_ok=True)
    source = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    recolored = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    part_records = []
    for part in sorted(recipe.get("parts", []), key=lambda item: int(item.get("draw_order", 0))):
        cutout_path = _resolve_path(recipe_path.parent, part.get("cutout"))
        if cutout_path is None or not cutout_path.exists():
            continue
        cutout = Image.open(cutout_path).convert("RGBA")
        if cutout.size != (width, height):
            cutout = cutout.resize((width, height), Image.Resampling.NEAREST)
        source.alpha_composite(cutout)
        material = DEFAULT_PART_MATERIALS.get(part.get("name"), "skin")
        part_recolored, stats = _recolor_cutout(
            cutout,
            palettes[material],
            outline_palette=palettes.get("outline", palettes.get("dark", [(0, 0, 0)])),
            outline_threshold=outline_threshold,
        )
        recolored.alpha_composite(part_recolored)
        part_records.append(
            {
                "part": part.get("name"),
                "material": material,
                "palette": [_rgb_to_hex(color) for color in palettes[material]],
                **stats,
            }
        )

    paths = {
        "source_copy": output / "mannequin_source_copy.png",
        "recolored": output / "mannequin_reference_recolored.png",
        "palette_swatches": output / "reference_palette_swatches.png",
        "contact_sheet": output / "mannequin_recolor_contact_sheet.png",
    }
    source.save(paths["source_copy"])
    recolored.save(paths["recolored"])
    _write_palette_swatches(palettes, paths["palette_swatches"])
    _write_contact_sheet(
        [
            ("mannequin copy", source),
            ("reference palette", Image.open(paths["palette_swatches"]).convert("RGBA")),
            ("recolored mannequin", recolored),
        ],
        paths["contact_sheet"],
    )

    manifest = {
        "schema": "glyph_lab.mannequin_recolor.v0",
        "source_mannequin": str(recipe_path),
        "style_recipe": str(style_path),
        "sprite_parts": str(sprite_parts_path) if sprite_parts_path is not None else None,
        "reference_part_colors": _sprite_part_colors(sprite_parts),
        "outline_threshold": outline_threshold,
        "part_materials": DEFAULT_PART_MATERIALS,
        "parts": part_records,
        "outputs": {key: str(path) for key, path in paths.items()},
        "rule": "copy mannequin cutouts and remap each part luminance into the reference-guy material palette",
    }
    manifest_path = output / "mannequin_recolor_manifest.json"
    _write_json(manifest_path, manifest)
    manifest["outputs"]["manifest"] = str(manifest_path)
    return manifest


def _recolor_cutout(
    cutout: Image.Image,
    palette: list[tuple[int, int, int]],
    *,
    outline_palette: list[tuple[int, int, int]],
    outline_threshold: int,
) -> tuple[Image.Image, dict[str, Any]]:
    pixels = cutout.load()
    luminances = []
    for y in range(cutout.height):
        for x in range(cutout.width):
            red, green, blue, alpha = pixels[x, y]
            if alpha:
                luminances.append(_luminance((red, green, blue)))
    output = Image.new("RGBA", cutout.size, (255, 255, 255, 0))
    if not luminances:
        return output, {"pixel_count": 0, "outline_pixels": 0, "luminance_range": None}
    low = min(luminances)
    high = max(luminances)
    target = output.load()
    outline_pixels = 0
    for y in range(cutout.height):
        for x in range(cutout.width):
            red, green, blue, alpha = pixels[x, y]
            if not alpha:
                continue
            luminance = _luminance((red, green, blue))
            if luminance <= outline_threshold:
                outline_pixels += 1
                color = outline_palette[0]
            else:
                color = _palette_color(luminance, palette, low, high)
            target[x, y] = (*color, alpha)
    return output, {
        "pixel_count": len(luminances),
        "outline_pixels": outline_pixels,
        "luminance_range": [round(low, 2), round(high, 2)],
    }


def _style_palettes(style: dict[str, Any]) -> dict[str, list[tuple[int, int, int]]]:
    palettes = {}
    for layer in style.get("layers", []):
        name = layer.get("name")
        palette = layer.get("palette")
        if isinstance(name, str) and isinstance(palette, list) and palette:
            palettes[name] = sorted([_hex_to_rgb(value) for value in palette], key=_luminance)
    return palettes


def _sprite_part_colors(sprite_parts: dict[str, Any] | None) -> dict[str, str]:
    if not sprite_parts:
        return {}
    colors = {}
    for layer in sprite_parts.get("layers", []):
        part = layer.get("part")
        average_hex = layer.get("average_hex")
        if part and average_hex:
            colors[part] = average_hex
    return colors


def _palette_color(
    luminance: float,
    palette: list[tuple[int, int, int]],
    low: float,
    high: float,
) -> tuple[int, int, int]:
    if len(palette) == 1 or high <= low:
        return palette[-1]
    normalized_lightness = (luminance - low) / (high - low)
    index = int(round(normalized_lightness * (len(palette) - 1)))
    return palette[max(0, min(len(palette) - 1, index))]


def _write_palette_swatches(palettes: dict[str, list[tuple[int, int, int]]], output_path: Path) -> None:
    names = [name for name in ("outline", "dark", "brown", "blue", "skin", "gray", "gold", "highlight") if name in palettes]
    row_height = 22
    swatch = 20
    width = 260
    height = max(1, len(names)) * row_height + 8
    image = Image.new("RGBA", (width, height), (245, 245, 245, 255))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    for row, name in enumerate(names):
        y = 4 + row * row_height
        draw.text((6, y + 5), name, fill=(0, 0, 0), font=font)
        for index, color in enumerate(palettes[name]):
            x = 78 + index * (swatch + 4)
            draw.rectangle((x, y, x + swatch, y + swatch), fill=color, outline=(0, 0, 0))
    image.save(output_path)


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
    sheet.save(output_path)


def _resolve_path(root: Path, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else root / path


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    text = value.strip().lstrip("#")
    if len(text) != 6:
        raise ValueError(f"expected #RRGGBB color, got {value!r}")
    return tuple(int(text[index : index + 2], 16) for index in (0, 2, 4))


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def _luminance(rgb: tuple[int, int, int]) -> float:
    red, green, blue = rgb
    return 0.299 * red + 0.587 * green + 0.114 * blue


def _load_json(path: str | Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
