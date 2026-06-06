from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from PIL import Image, ImageDraw

from .ascii_glyph_renderer import _border_median_rgb, _median, _rgb_distance
from .color_family_layers import classify_color_family
from .foreground_mask import FOREGROUND_MODES, foreground_mask, write_foreground_mask


REGION_LANES = (
    "outline",
    "head",
    "neck",
    "torso",
    "pelvis",
    "upper_arm_left",
    "lower_arm_left",
    "hand_left",
    "upper_arm_right",
    "lower_arm_right",
    "hand_right",
    "upper_leg_left",
    "lower_leg_left",
    "foot_left",
    "upper_leg_right",
    "lower_leg_right",
    "foot_right",
    "unassigned_foreground",
)

STACK_ORDER = (
    "head",
    "neck",
    "torso",
    "pelvis",
    "upper_leg_left",
    "lower_leg_left",
    "foot_left",
    "upper_leg_right",
    "lower_leg_right",
    "foot_right",
    "upper_arm_left",
    "lower_arm_left",
    "hand_left",
    "upper_arm_right",
    "lower_arm_right",
    "hand_right",
    "unassigned_foreground",
    "outline",
)


def classify_humanoid_regions(
    image_path: str | Path,
    output_dir: str | Path,
    *,
    foreground_mode: str = "auto",
    foreground_alpha_threshold: int = 1,
    foreground_background_threshold: int = 22,
    background_threshold: int = 22,
    scale: int = 2,
) -> dict[str, Any]:
    if foreground_mode not in FOREGROUND_MODES:
        raise ValueError(f"unknown foreground mode {foreground_mode!r}; expected one of {sorted(FOREGROUND_MODES)}")
    if scale < 1:
        raise ValueError("scale must be at least 1")

    output = Path(output_dir)
    masks_dir = output / "masks"
    cutouts_dir = output / "cutouts"
    groups_dir = output / "groups"
    composites_dir = output / "composites"
    for directory in (masks_dir, cutouts_dir, groups_dir, composites_dir):
        directory.mkdir(parents=True, exist_ok=True)

    with Image.open(image_path) as source:
        image = source.convert("RGBA")
    background = _border_median_rgb(image)
    foreground, foreground_summary = foreground_mask(
        image,
        image.width,
        image.height,
        mode=foreground_mode,
        alpha_threshold=foreground_alpha_threshold,
        background_threshold=foreground_background_threshold,
    )
    foreground_mask_path = masks_dir / "foreground_mask.png"
    write_foreground_mask(foreground, foreground_mask_path, scale=scale)
    bbox = _mask_bbox(foreground)

    lane_grid = _classify_pixels(
        image,
        foreground,
        bbox,
        background=background,
        background_threshold=background_threshold,
    )
    masks = {
        lane: [[lane_grid[y][x]["lane"] == lane for x in range(image.width)] for y in range(image.height)]
        for lane in REGION_LANES
    }

    layers = []
    rendered_layers: dict[str, Image.Image] = {}
    for lane in REGION_LANES:
        mask = masks[lane]
        mask_path = masks_dir / f"{lane}_mask.png"
        cutout_path = cutouts_dir / f"{lane}_cutout.png"
        cropped_cutout_path = cutouts_dir / f"{lane}_cropped.png"
        _write_mask(mask, mask_path, scale=scale)
        cutout = _render_cutout(image, mask)
        rendered_layers[lane] = cutout
        _save_scaled(cutout, cutout_path, scale)
        lane_bbox = _mask_bbox(mask)
        _save_scaled(_crop_to_bbox(cutout, lane_bbox), cropped_cutout_path, scale)
        average_rgb = _average_lane_rgb(lane_grid, lane)
        layers.append(
            {
                "lane": lane,
                "pixels": _mask_count(mask),
                "bbox": list(lane_bbox) if lane_bbox else None,
                "average_rgb": list(average_rgb) if average_rgb else None,
                "average_hex": _hex_rgb(average_rgb),
                "mask": str(mask_path),
                "cutout": str(cutout_path),
                "cropped_cutout": str(cropped_cutout_path),
                "components": _connected_components(mask),
            }
        )

    groups = _write_groups(image, masks, groups_dir, scale=scale)
    stack = Image.new("RGBA", image.size, (255, 255, 255, 0))
    for lane in STACK_ORDER:
        stack.alpha_composite(rendered_layers[lane])
    stacked_path = composites_dir / "stacked_humanoid_regions.png"
    _save_scaled(stack, stacked_path, scale)
    contact_sheet_path = output / "humanoid_region_contact_sheet.png"

    manifest = {
        "source_image": str(image_path),
        "width": image.width,
        "height": image.height,
        "background_rgb": list(background),
        "background_threshold": background_threshold,
        "foreground": {**foreground_summary, "mask": str(foreground_mask_path)},
        "occupied_bbox_pixels": list(bbox) if bbox else None,
        "lanes": list(REGION_LANES),
        "stack_order": list(STACK_ORDER),
        "rule": "humanoid region lanes from region-color evidence plus silhouette bbox, centerline, side, and vertical body bands",
        "layers": layers,
        "groups": groups,
        "stacked": str(stacked_path),
        "contact_sheet": str(contact_sheet_path),
    }
    _write_contact_sheet(image_path, manifest, contact_sheet_path)
    _write_json(output / "humanoid_regions.json", manifest)
    return manifest


def _classify_pixels(
    image: Image.Image,
    foreground: list[list[bool]],
    bbox: tuple[int, int, int, int] | None,
    *,
    background: tuple[int, int, int],
    background_threshold: int,
) -> list[list[dict[str, Any]]]:
    width, height = image.size
    grid = [[{"lane": None, "family": None, "rgb": None} for _ in range(width)] for _ in range(height)]
    if bbox is None:
        return grid
    x0, y0, x1, y1 = bbox
    occupied_width = max(1, x1 - x0 + 1)
    occupied_height = max(1, y1 - y0 + 1)
    center_x = (x0 + x1) / 2.0
    pixels = image.load()
    for y in range(height):
        y_rel = (y - y0) / occupied_height
        for x in range(width):
            if not foreground[y][x]:
                continue
            rgb = pixels[x, y][:3]
            if _rgb_distance(rgb, background) <= background_threshold:
                continue
            family = classify_color_family(rgb, background_rgb=background, background_threshold=background_threshold)
            lane = _lane_for_pixel(
                family,
                x,
                y_rel,
                center_x=center_x,
                occupied_width=occupied_width,
            )
            grid[y][x] = {"lane": lane, "family": family, "rgb": rgb}
    return grid


def _lane_for_pixel(
    family: str | None,
    x: int,
    y_rel: float,
    *,
    center_x: float,
    occupied_width: int,
) -> str:
    if family is None:
        return "unassigned_foreground"
    if family == "dark":
        return "outline"

    x_rel = (x - center_x) / occupied_width
    side = "left" if x < center_x else "right"
    abs_x = abs(x_rel)
    central = abs_x <= 0.20
    limb_side = abs_x > 0.18

    if y_rel < 0.22:
        return "head"
    if 0.20 <= y_rel < 0.31 and central:
        return "neck"
    if 0.23 <= y_rel < 0.48 and central:
        return "torso"
    if 0.44 <= y_rel < 0.59 and central:
        return "pelvis"

    if 0.20 <= y_rel < 0.65 and limb_side:
        if y_rel >= 0.52:
            return f"hand_{side}"
        if y_rel >= 0.39:
            return f"lower_arm_{side}"
        return f"upper_arm_{side}"

    if y_rel >= 0.56:
        if y_rel >= 0.87:
            return f"foot_{side}"
        if y_rel >= 0.73:
            return f"lower_leg_{side}"
        return f"upper_leg_{side}"

    return "unassigned_foreground"


def _render_cutout(image: Image.Image, mask: list[list[bool]]) -> Image.Image:
    output = Image.new("RGBA", image.size, (255, 255, 255, 0))
    source = image.load()
    target = output.load()
    for y, row in enumerate(mask):
        for x, keep in enumerate(row):
            if keep:
                target[x, y] = source[x, y]
    return output


def _crop_to_bbox(image: Image.Image, bbox: tuple[int, int, int, int] | None, *, pad: int = 2) -> Image.Image:
    if bbox is None:
        return Image.new("RGBA", (1, 1), (255, 255, 255, 0))
    x0, y0, x1, y1 = bbox
    return image.crop(
        (
            max(0, x0 - pad),
            max(0, y0 - pad),
            min(image.width, x1 + pad + 1),
            min(image.height, y1 + pad + 1),
        )
    )


def _write_groups(
    image: Image.Image,
    masks: dict[str, list[list[bool]]],
    output_dir: Path,
    *,
    scale: int,
) -> list[dict[str, Any]]:
    group_defs = {
        "body_core": ("neck", "torso", "pelvis"),
        "arm_left": ("upper_arm_left", "lower_arm_left", "hand_left"),
        "arm_right": ("upper_arm_right", "lower_arm_right", "hand_right"),
        "arms": (
            "upper_arm_left",
            "lower_arm_left",
            "hand_left",
            "upper_arm_right",
            "lower_arm_right",
            "hand_right",
        ),
        "leg_left": ("upper_leg_left", "lower_leg_left", "foot_left"),
        "leg_right": ("upper_leg_right", "lower_leg_right", "foot_right"),
        "legs": (
            "upper_leg_left",
            "lower_leg_left",
            "foot_left",
            "upper_leg_right",
            "lower_leg_right",
            "foot_right",
        ),
        "body_without_outline": tuple(lane for lane in REGION_LANES if lane not in {"outline", "unassigned_foreground"}),
    }
    groups = []
    built_masks: dict[str, list[list[bool]]] = {}
    for group, lanes in group_defs.items():
        if group == "arms":
            mask = _union_masks([built_masks["arm_left"], built_masks["arm_right"]])
        elif group == "legs":
            mask = _union_masks([built_masks["leg_left"], built_masks["leg_right"]])
        else:
            mask = _union_masks([masks[lane] for lane in lanes])
        if group in {"body_core", "arm_left", "arm_right", "leg_left", "leg_right"}:
            mask = _largest_component_mask(mask)
        built_masks[group] = mask
        mask_path = output_dir / f"{group}_mask.png"
        cutout_path = output_dir / f"{group}_cutout.png"
        cropped_cutout_path = output_dir / f"{group}_cropped.png"
        _write_mask(mask, mask_path, scale=scale)
        cutout = _render_cutout(image, mask)
        _save_scaled(cutout, cutout_path, scale)
        group_bbox = _mask_bbox(mask)
        _save_scaled(_crop_to_bbox(cutout, group_bbox), cropped_cutout_path, scale)
        groups.append(
            {
                "group": group,
                "lanes": list(lanes),
                "pixels": _mask_count(mask),
                "bbox": list(group_bbox) if group_bbox else None,
                "mask": str(mask_path),
                "cutout": str(cutout_path),
                "cropped_cutout": str(cropped_cutout_path),
            }
        )
    return groups


def _union_masks(masks: list[list[list[bool]]]) -> list[list[bool]]:
    if not masks:
        return []
    height = len(masks[0])
    width = len(masks[0][0]) if height else 0
    return [
        [any(mask[y][x] for mask in masks) for x in range(width)]
        for y in range(height)
    ]


def _largest_component_mask(mask: list[list[bool]]) -> list[list[bool]]:
    components = _component_cells(mask)
    if not components:
        return mask
    largest = max(components, key=len)
    height = len(mask)
    width = len(mask[0]) if height else 0
    output = [[False for _ in range(width)] for _ in range(height)]
    for x, y in largest:
        output[y][x] = True
    return output


def _write_contact_sheet(image_path: str | Path, manifest: dict[str, Any], output_path: str | Path) -> None:
    visible_layers = [layer for layer in manifest["layers"] if layer["pixels"] > 0]
    thumb_w = 150
    thumb_h = 260
    pad = 12
    label_h = 42
    cells = [("original", str(image_path), ""), ("stacked", manifest["stacked"], "all lanes")]
    cells.extend((layer["lane"], layer["cropped_cutout"], f"{layer['pixels']} px {layer['average_hex'] or ''}") for layer in visible_layers)
    columns = 5
    rows = max(1, (len(cells) + columns - 1) // columns)
    sheet = Image.new("RGB", (pad + columns * (thumb_w + pad), pad + rows * (thumb_h + label_h + pad)), "white")
    draw = ImageDraw.Draw(sheet)
    for index, (label, path, subtitle) in enumerate(cells):
        column = index % columns
        row = index // columns
        x = pad + column * (thumb_w + pad)
        y = pad + row * (thumb_h + label_h + pad)
        draw.text((x, y), label, fill="black")
        if subtitle:
            draw.text((x, y + 15), subtitle[:24], fill="black")
        with Image.open(path) as image:
            view = image.convert("RGBA")
            view.thumbnail((thumb_w, thumb_h), Image.Resampling.NEAREST)
            canvas = Image.new("RGBA", (thumb_w, thumb_h), (255, 255, 255, 255))
            canvas.alpha_composite(view, ((thumb_w - view.width) // 2, (thumb_h - view.height) // 2))
            sheet.paste(canvas.convert("RGB"), (x, y + label_h))
        draw.rectangle([x, y + label_h, x + thumb_w - 1, y + label_h + thumb_h - 1], outline=(210, 210, 210))
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


def _connected_components(mask: list[list[bool]]) -> list[dict[str, Any]]:
    components = []
    for cells in _component_cells(mask):
        xs = [cell[0] for cell in cells]
        ys = [cell[1] for cell in cells]
        components.append({"pixels": len(cells), "bbox": [min(xs), min(ys), max(xs), max(ys)]})
    components.sort(key=lambda item: item["pixels"], reverse=True)
    return components


def _component_cells(mask: list[list[bool]]) -> list[list[tuple[int, int]]]:
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
            components.append(cells)
    return components


def _mask_bbox(mask: list[list[bool]]) -> tuple[int, int, int, int] | None:
    points = [(x, y) for y, row in enumerate(mask) for x, value in enumerate(row) if value]
    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def _mask_count(mask: list[list[bool]]) -> int:
    return sum(1 for row in mask for value in row if value)


def _average_lane_rgb(grid: list[list[dict[str, Any]]], lane: str) -> tuple[int, int, int] | None:
    colors = [cell["rgb"] for row in grid for cell in row if cell["lane"] == lane and cell["rgb"] is not None]
    if not colors:
        return None
    return tuple(_median([color[channel] for color in colors]) for channel in range(3))


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
