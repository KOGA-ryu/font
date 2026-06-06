from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from PIL import Image, ImageDraw

from .mannequin import BODY_PARTS, PARENT_BY_PART, _pivot_for_part


BASE_WIDTH = 128
BASE_HEIGHT = 192

PART_SHAPES: dict[str, dict[str, Any]] = {
    "head": {"kind": "ellipse", "bbox": [48, 10, 80, 48]},
    "neck": {"kind": "rect", "bbox": [58, 50, 70, 60]},
    "torso": {"kind": "polygon", "points": [[50, 62], [78, 62], [76, 94], [52, 94]]},
    "pelvis": {"kind": "polygon", "points": [[51, 96], [77, 96], [74, 112], [54, 112]]},
    "upper_arm_left": {"kind": "polygon", "points": [[39, 59], [49, 63], [45, 87], [34, 85]]},
    "lower_arm_left": {"kind": "polygon", "points": [[33, 88], [44, 90], [39, 108], [28, 106]]},
    "hand_left": {"kind": "ellipse", "bbox": [24, 107, 40, 124]},
    "upper_arm_right": {"kind": "polygon", "points": [[79, 63], [89, 59], [94, 85], [83, 87]]},
    "lower_arm_right": {"kind": "polygon", "points": [[84, 90], [95, 88], [100, 106], [89, 108]]},
    "hand_right": {"kind": "ellipse", "bbox": [88, 107, 104, 124]},
    "upper_leg_left": {"kind": "polygon", "points": [[49, 113], [62, 113], [60, 139], [46, 139]]},
    "lower_leg_left": {"kind": "polygon", "points": [[45, 140], [60, 140], [57, 164], [42, 164]]},
    "foot_left": {"kind": "polygon", "points": [[41, 165], [59, 165], [62, 184], [30, 184]]},
    "upper_leg_right": {"kind": "polygon", "points": [[66, 113], [79, 113], [82, 139], [68, 139]]},
    "lower_leg_right": {"kind": "polygon", "points": [[68, 140], [83, 140], [86, 164], [71, 164]]},
    "foot_right": {"kind": "polygon", "points": [[69, 165], [87, 165], [98, 184], [66, 184]]},
}

SIDE_PART_SHAPES: dict[str, dict[str, Any]] = {
    "head": {"kind": "polygon", "points": [[55, 12], [71, 9], [82, 17], [87, 27], [82, 31], [80, 42], [70, 49], [58, 46], [51, 35], [51, 22]]},
    "neck": {"kind": "rect", "bbox": [62, 50, 72, 61]},
    "torso": {"kind": "polygon", "points": [[58, 63], [76, 64], [78, 94], [60, 95]]},
    "pelvis": {"kind": "polygon", "points": [[59, 97], [78, 97], [76, 113], [61, 113]]},
    "upper_arm_left": {"kind": "polygon", "points": [[55, 65], [64, 67], [62, 90], [52, 88]]},
    "lower_arm_left": {"kind": "polygon", "points": [[52, 90], [62, 92], [59, 113], [49, 111]]},
    "hand_left": {"kind": "ellipse", "bbox": [46, 110, 62, 126]},
    "upper_arm_right": {"kind": "polygon", "points": [[74, 65], [84, 69], [81, 92], [70, 89]]},
    "lower_arm_right": {"kind": "polygon", "points": [[70, 91], [81, 94], [81, 116], [69, 113]]},
    "hand_right": {"kind": "ellipse", "bbox": [67, 112, 84, 129]},
    "upper_leg_left": {"kind": "polygon", "points": [[58, 114], [69, 114], [67, 140], [54, 140]]},
    "lower_leg_left": {"kind": "polygon", "points": [[53, 141], [67, 141], [65, 166], [51, 166]]},
    "foot_left": {"kind": "polygon", "points": [[50, 167], [67, 167], [79, 184], [47, 184]]},
    "upper_leg_right": {"kind": "polygon", "points": [[68, 114], [80, 114], [82, 140], [69, 140]]},
    "lower_leg_right": {"kind": "polygon", "points": [[69, 141], [83, 141], [87, 166], [73, 166]]},
    "foot_right": {"kind": "polygon", "points": [[72, 167], [89, 167], [103, 184], [70, 184]]},
}

REGION_COLORS = {
    "head": (238, 188, 80),
    "neck": (32, 75, 155),
    "torso": (75, 105, 170),
    "pelvis": (210, 60, 45),
    "upper_arm_left": (230, 120, 160),
    "lower_arm_left": (218, 131, 73),
    "hand_left": (96, 180, 78),
    "upper_arm_right": (96, 180, 78),
    "lower_arm_right": (169, 194, 84),
    "hand_right": (90, 190, 190),
    "upper_leg_left": (220, 174, 40),
    "lower_leg_left": (169, 194, 84),
    "foot_left": (96, 180, 78),
    "upper_leg_right": (218, 131, 73),
    "lower_leg_right": (210, 60, 45),
    "foot_right": (160, 75, 230),
}

PREVIEW_COLORS = {
    "head": (229, 219, 193),
    "neck": (217, 206, 180),
    "torso": (224, 214, 188),
    "pelvis": (214, 203, 177),
    "upper_arm_left": (220, 210, 184),
    "lower_arm_left": (214, 204, 178),
    "hand_left": (224, 214, 188),
    "upper_arm_right": (220, 210, 184),
    "lower_arm_right": (214, 204, 178),
    "hand_right": (224, 214, 188),
    "upper_leg_left": (218, 208, 182),
    "lower_leg_left": (211, 201, 175),
    "foot_left": (224, 214, 188),
    "upper_leg_right": (218, 208, 182),
    "lower_leg_right": (211, 201, 175),
    "foot_right": (224, 214, 188),
}

DRAW_ORDER = (
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
    "pelvis",
    "torso",
    "neck",
    "head",
)


def generate_front_mannequin_template(
    output_path: str | Path,
    *,
    width: int = BASE_WIDTH,
    height: int = BASE_HEIGHT,
    scale: int = 2,
) -> dict[str, Any]:
    return generate_mannequin_template(output_path, width=width, height=height, scale=scale, view="front")


def generate_mannequin_template(
    output_path: str | Path,
    *,
    width: int = BASE_WIDTH,
    height: int = BASE_HEIGHT,
    scale: int = 2,
    view: str = "front",
) -> dict[str, Any]:
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive")
    if scale < 1:
        raise ValueError("scale must be at least 1")
    shape_set = _shape_set_for_view(view)

    output = Path(output_path)
    output.mkdir(parents=True, exist_ok=True)
    preview = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    region_map = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    preview_draw = ImageDraw.Draw(preview)
    region_draw = ImageDraw.Draw(region_map)

    parts = []
    for name in DRAW_ORDER:
        shape = _scale_shape(shape_set[name], width, height)
        bbox = _shape_bbox(shape)
        _draw_shape(region_draw, shape, fill=REGION_COLORS[name], outline=None, width=1)
        _draw_shape(preview_draw, shape, fill=PREVIEW_COLORS[name], outline=(35, 35, 35), width=max(1, round(width / 96)))
        parts.append(
            {
                "name": name,
                "parent": PARENT_BY_PART[name],
                "bbox": bbox,
                "pivot": _pivot_for_part(name, bbox),
                "region_rgb": list(REGION_COLORS[name]),
                "preview_rgb": list(PREVIEW_COLORS[name]),
            }
        )

    _draw_preview_guides(preview_draw, parts, width)

    preview_path = output / f"{view}_mannequin_template.png"
    region_path = output / f"{view}_mannequin_region_map.png"
    _save_scaled(preview, preview_path, scale)
    _save_scaled(region_map, region_path, scale)

    manifest = {
        "schema": "glyph_lab.mannequin_template.v0",
        "template": f"{view}_humanoid_mannequin",
        "view": view,
        "width": width,
        "height": height,
        "scale": scale,
        "parts": sorted(parts, key=lambda item: BODY_PARTS.index(item["name"])),
        "draw_order": list(DRAW_ORDER),
        "outputs": {
            "preview": str(preview_path),
            "region_map": str(region_path),
        },
        "rule": "deterministic geometry creates the mannequin source; generated images are references only, not assets",
    }
    manifest_path = output / "mannequin_template_manifest.json"
    _write_json(manifest_path, manifest)
    manifest["outputs"]["manifest"] = str(manifest_path)
    return manifest


def _shape_set_for_view(view: str) -> dict[str, dict[str, Any]]:
    if view == "front":
        return PART_SHAPES
    if view == "side":
        return SIDE_PART_SHAPES
    raise ValueError("unknown mannequin template view {!r}; expected 'front' or 'side'".format(view))


def _draw_preview_guides(draw: ImageDraw.ImageDraw, parts: list[dict[str, Any]], width: int) -> None:
    radius = max(1, round(width / 96))
    for part in parts:
        x, y = part["pivot"]
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(80, 130, 180), outline=(255, 255, 255))


def _draw_shape(
    draw: ImageDraw.ImageDraw,
    shape: dict[str, Any],
    *,
    fill: tuple[int, int, int],
    outline: tuple[int, int, int] | None,
    width: int,
) -> None:
    kind = shape["kind"]
    if kind == "ellipse":
        draw.ellipse(shape["bbox"], fill=fill, outline=outline, width=width)
        return
    if kind == "rect":
        draw.rectangle(shape["bbox"], fill=fill, outline=outline, width=width)
        return
    if kind == "polygon":
        draw.polygon(shape["points"], fill=fill, outline=outline)
        if outline is not None and width > 1:
            draw.line(shape["points"] + [shape["points"][0]], fill=outline, width=width)
        return
    raise ValueError(f"unknown mannequin shape kind {kind!r}")


def _scale_shape(shape: dict[str, Any], width: int, height: int) -> dict[str, Any]:
    sx = width / BASE_WIDTH
    sy = height / BASE_HEIGHT
    if shape["kind"] in {"ellipse", "rect"}:
        return {"kind": shape["kind"], "bbox": [_scale_x(value, sx) if index % 2 == 0 else _scale_y(value, sy) for index, value in enumerate(shape["bbox"])]}
    if shape["kind"] == "polygon":
        return {"kind": "polygon", "points": [[_scale_x(x, sx), _scale_y(y, sy)] for x, y in shape["points"]]}
    raise ValueError(f"unknown mannequin shape kind {shape['kind']!r}")


def _shape_bbox(shape: dict[str, Any]) -> list[int]:
    if shape["kind"] in {"ellipse", "rect"}:
        return [int(value) for value in shape["bbox"]]
    xs = [point[0] for point in shape["points"]]
    ys = [point[1] for point in shape["points"]]
    return [min(xs), min(ys), max(xs), max(ys)]


def _scale_x(value: int, scale: float) -> int:
    return int(round(value * scale))


def _scale_y(value: int, scale: float) -> int:
    return int(round(value * scale))


def _save_scaled(image: Image.Image, path: Path, scale: int) -> None:
    image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST).save(path)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
