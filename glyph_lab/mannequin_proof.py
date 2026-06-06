from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import math

from PIL import Image, ImageDraw, ImageFont


PART_COLORS = (
    (231, 76, 60),
    (52, 152, 219),
    (46, 204, 113),
    (241, 196, 15),
    (155, 89, 182),
    (230, 126, 34),
    (26, 188, 156),
    (52, 73, 94),
    (142, 68, 173),
    (39, 174, 96),
    (41, 128, 185),
    (243, 156, 18),
    (192, 57, 43),
    (22, 160, 133),
    (127, 140, 141),
    (211, 84, 0),
)


def render_mannequin_proof(
    mannequin_path: str | Path,
    output_path: str | Path,
    *,
    scale: int = 2,
) -> dict[str, Any]:
    recipe_path = Path(mannequin_path)
    recipe = _load_json(recipe_path)
    output = Path(output_path)
    output.mkdir(parents=True, exist_ok=True)
    width = int(recipe.get("grid", {}).get("width", 0))
    height = int(recipe.get("grid", {}).get("height", 0))
    if width <= 0 or height <= 0:
        raise ValueError("mannequin recipe must include positive grid width and height")

    parts = sorted(recipe.get("parts", []), key=lambda item: int(item.get("draw_order", 0)))
    if not parts:
        raise ValueError("mannequin recipe has no body parts to render")

    loaded_parts, warnings = _load_part_masks(parts, recipe_path.parent, width, height)
    silhouette = _render_silhouette(width, height, loaded_parts)
    shaded_parts = _render_shaded_parts(width, height, loaded_parts)
    part_overlay = _render_part_overlay(width, height, loaded_parts)
    skeleton_overlay = _render_skeleton_overlay(width, height, loaded_parts, recipe)

    paths = {
        "silhouette": output / "mannequin_silhouette.png",
        "shaded_parts": output / "mannequin_shaded_parts.png",
        "parts_overlay": output / "mannequin_parts_overlay.png",
        "skeleton_overlay": output / "mannequin_skeleton_overlay.png",
        "contact_sheet": output / "mannequin_contact_sheet.png",
    }
    _save_scaled(silhouette, paths["silhouette"], scale)
    _save_scaled(shaded_parts, paths["shaded_parts"], scale)
    _save_scaled(part_overlay, paths["parts_overlay"], scale)
    _save_scaled(skeleton_overlay, paths["skeleton_overlay"], scale)
    _write_contact_sheet(
        [
            ("silhouette", silhouette),
            ("shaded source", shaded_parts),
            ("parts overlay", part_overlay),
            ("skeleton overlay", skeleton_overlay),
        ],
        paths["contact_sheet"],
        scale,
    )

    manifest = {
        "schema": "glyph_lab.mannequin_proof.v0",
        "source_mannequin": str(recipe_path),
        "pose": recipe.get("pose"),
        "grid": {"width": width, "height": height},
        "part_count": len(loaded_parts),
        "draw_order": [part["name"] for part in loaded_parts],
        "skeleton": {
            "joint_count": len(recipe.get("skeleton", {}).get("joints", {})),
            "edge_count": len(recipe.get("skeleton", {}).get("edges", [])),
        },
        "outputs": {name: str(path) for name, path in paths.items()},
        "shading_summary": {
            part["name"]: part["_shading_summary"]
            for part in loaded_parts
            if part.get("_shading_summary") is not None
        },
        "warnings": warnings,
    }
    manifest_path = output / "proof_manifest.json"
    _write_json(manifest_path, manifest)
    manifest["outputs"]["manifest"] = str(manifest_path)
    return manifest


def _load_part_masks(
    parts: list[dict[str, Any]],
    recipe_root: Path,
    width: int,
    height: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    loaded_parts = []
    warnings = []
    for index, part in enumerate(parts):
        mask_path = _resolve_path(recipe_root, part.get("mask"))
        if mask_path is None or not mask_path.exists():
            warnings.append(f"missing mask for {part.get('name')}: {mask_path}")
            continue
        mask = _load_mask(mask_path, width, height)
        loaded = dict(part)
        loaded["_mask"] = mask
        loaded["_color"] = PART_COLORS[index % len(PART_COLORS)]
        cutout_path = _resolve_path(recipe_root, part.get("cutout"))
        if cutout_path is not None and cutout_path.exists():
            cutout = _load_cutout(cutout_path, width, height, mask)
            loaded["_cutout"] = cutout
            loaded["_shading_summary"] = _shading_summary(cutout, mask)
        else:
            loaded["_cutout"] = None
            loaded["_shading_summary"] = None
            warnings.append(f"missing cutout for {part.get('name')}: {cutout_path}")
        loaded_parts.append(loaded)
    return loaded_parts, warnings


def _render_silhouette(width: int, height: int, parts: list[dict[str, Any]]) -> Image.Image:
    image = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    union = Image.new("L", (width, height), 0)
    for part in parts:
        union = Image.composite(Image.new("L", (width, height), 255), union, part["_mask"])
    ink = Image.new("RGBA", (width, height), (0, 0, 0, 255))
    image = Image.composite(ink, image, union)
    return image


def _render_shaded_parts(width: int, height: int, parts: list[dict[str, Any]]) -> Image.Image:
    image = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    for part in parts:
        cutout = part.get("_cutout")
        if cutout is not None:
            image.alpha_composite(cutout)
    return image


def _render_part_overlay(width: int, height: int, parts: list[dict[str, Any]]) -> Image.Image:
    image = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    for part in parts:
        _alpha_part(image, part, alpha=178)
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    for part in parts:
        _draw_bbox(draw, part, (0, 0, 0))
        x, y = _label_point(part)
        draw.text((x, y), part["name"], fill=(0, 0, 0), font=font)
    return image


def _render_skeleton_overlay(width: int, height: int, parts: list[dict[str, Any]], recipe: dict[str, Any]) -> Image.Image:
    image = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    for part in parts:
        _alpha_part(image, part, alpha=72)
    draw = ImageDraw.Draw(image)
    skeleton = recipe.get("skeleton", {})
    joints = skeleton.get("joints", {})
    edges = skeleton.get("edges", [])
    line_width = max(1, round(min(width, height) / 80))
    if edges:
        for a, b in edges:
            if a in joints and b in joints:
                draw.line((_point(joints[a]), _point(joints[b])), fill=(25, 25, 25), width=line_width)
    else:
        _draw_parent_pivot_skeleton(draw, parts, line_width)
    for part in parts:
        _draw_bbox(draw, part, (60, 60, 60))
    used_joint_names = {name for edge in edges for name in edge} if edges else set(joints)
    for name in used_joint_names:
        if name in joints:
            _draw_dot(draw, _point(joints[name]), (220, 35, 35), radius=max(2, round(min(width, height) / 120)))
    return image


def _draw_parent_pivot_skeleton(draw: ImageDraw.ImageDraw, parts: list[dict[str, Any]], line_width: int) -> None:
    by_name = {part["name"]: part for part in parts}
    for part in parts:
        parent = by_name.get(part.get("parent"))
        if parent is not None:
            draw.line((_point(part["pivot"]), _point(parent["pivot"])), fill=(25, 25, 25), width=line_width)


def _alpha_part(image: Image.Image, part: dict[str, Any], *, alpha: int) -> None:
    color = part["_color"]
    layer = Image.new("RGBA", image.size, (*color, 0))
    layer.putalpha(part["_mask"].point(lambda value: alpha if value else 0))
    image.alpha_composite(layer)


def _draw_bbox(draw: ImageDraw.ImageDraw, part: dict[str, Any], color: tuple[int, int, int]) -> None:
    bbox = part.get("bbox")
    if not bbox:
        return
    x0, y0, x1, y1 = [int(value) for value in bbox]
    draw.rectangle((x0, y0, x1, y1), outline=color, width=1)


def _draw_dot(
    draw: ImageDraw.ImageDraw,
    point: tuple[int, int],
    color: tuple[int, int, int],
    *,
    radius: int,
) -> None:
    x, y = point
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color, outline=(255, 255, 255))


def _write_contact_sheet(items: list[tuple[str, Image.Image]], output_path: Path, scale: int) -> None:
    scaled = [(name, image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST)) for name, image in items]
    label_height = 18
    padding = 12
    cell_width = max(image.width for _, image in scaled)
    cell_height = max(image.height for _, image in scaled) + label_height
    sheet = Image.new(
        "RGBA",
        (padding + len(scaled) * (cell_width + padding), padding + cell_height + padding),
        (245, 245, 245, 255),
    )
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    x = padding
    for name, image in scaled:
        draw.text((x, padding), name, fill=(0, 0, 0), font=font)
        sheet.alpha_composite(image, (x, padding + label_height))
        x += cell_width + padding
    sheet.save(output_path)


def _save_scaled(image: Image.Image, output_path: Path, scale: int) -> None:
    if scale < 1:
        raise ValueError("scale must be at least 1")
    scaled = image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST)
    scaled.save(output_path)


def _load_mask(path: Path, width: int, height: int) -> Image.Image:
    image = Image.open(path)
    if image.mode == "RGBA":
        alpha = image.getchannel("A")
        gray = image.convert("L")
        mask = Image.composite(gray, Image.new("L", image.size, 0), alpha)
    else:
        mask = image.convert("L")
    if mask.size != (width, height):
        mask = mask.resize((width, height), Image.Resampling.NEAREST)
    return mask.point(lambda value: 255 if value > 0 else 0)


def _load_cutout(path: Path, width: int, height: int, mask: Image.Image) -> Image.Image:
    image = Image.open(path).convert("RGBA")
    if image.size != (width, height):
        image = image.resize((width, height), Image.Resampling.NEAREST)
    alpha = Image.composite(mask, Image.new("L", mask.size, 0), image.getchannel("A"))
    image.putalpha(alpha)
    return image


def _shading_summary(cutout: Image.Image, mask: Image.Image) -> dict[str, Any]:
    values = []
    cutout_pixels = cutout.load()
    mask_pixels = mask.load()
    for y in range(cutout.height):
        for x in range(cutout.width):
            if mask_pixels[x, y]:
                r, g, b, a = cutout_pixels[x, y]
                if a:
                    values.append(round(0.2126 * r + 0.7152 * g + 0.0722 * b))
    if not values:
        return {
            "pixel_count": 0,
            "average_luminance": None,
            "min_luminance": None,
            "max_luminance": None,
            "luminance_range": None,
        }
    minimum = min(values)
    maximum = max(values)
    return {
        "pixel_count": len(values),
        "average_luminance": round(sum(values) / len(values), 2),
        "min_luminance": minimum,
        "max_luminance": maximum,
        "luminance_range": maximum - minimum,
    }


def _resolve_path(root: Path, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else root / path


def _label_point(part: dict[str, Any]) -> tuple[int, int]:
    bbox = part.get("bbox")
    if bbox:
        return int(bbox[0]), max(0, int(bbox[1]) - 9)
    return _point(part.get("pivot", [0, 0]))


def _point(values: Any) -> tuple[int, int]:
    if not values:
        return (0, 0)
    x, y = values
    if isinstance(x, float) and math.isnan(x):
        x = 0
    if isinstance(y, float) and math.isnan(y):
        y = 0
    return (int(round(x)), int(round(y)))


def _load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: str | Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
