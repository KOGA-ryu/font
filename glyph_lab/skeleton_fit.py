from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import math

from PIL import Image, ImageDraw, ImageFont


JOINT_SOURCE_PARTS: dict[str, list[str]] = {
    "neck": ["head", "neck"],
    "chest": ["torso"],
    "pelvis": ["pelvis"],
    "shoulder_left": ["upper_arm_left", "torso"],
    "elbow_left": ["upper_arm_left", "lower_arm_left"],
    "wrist_left": ["lower_arm_left", "hand_left"],
    "hand_left": ["hand_left"],
    "shoulder_right": ["upper_arm_right", "torso"],
    "elbow_right": ["upper_arm_right", "lower_arm_right"],
    "wrist_right": ["lower_arm_right", "hand_right"],
    "hand_right": ["hand_right"],
    "hip_left": ["pelvis", "upper_leg_left"],
    "knee_left": ["upper_leg_left", "lower_leg_left"],
    "ankle_left": ["lower_leg_left", "foot_left"],
    "foot_left": ["foot_left"],
    "hip_right": ["pelvis", "upper_leg_right"],
    "knee_right": ["upper_leg_right", "lower_leg_right"],
    "ankle_right": ["lower_leg_right", "foot_right"],
    "foot_right": ["foot_right"],
}


def fit_skeleton(
    mannequin_path: str | Path,
    output_path: str | Path,
    *,
    scale: int = 1,
) -> dict[str, Any]:
    recipe_path = Path(mannequin_path)
    recipe = _load_json(recipe_path)
    width = int(recipe.get("grid", {}).get("width", 0))
    height = int(recipe.get("grid", {}).get("height", 0))
    if width <= 0 or height <= 0:
        raise ValueError("mannequin recipe must include positive grid width and height")
    if scale < 1:
        raise ValueError("scale must be at least 1")

    output = Path(output_path)
    output.mkdir(parents=True, exist_ok=True)
    parts = _load_parts(recipe.get("parts", []), recipe_path.parent, width, height)
    joints = recipe.get("skeleton", {}).get("joints", {})
    edges = recipe.get("skeleton", {}).get("edges", [])
    fitted_joints = _fit_joints(joints, parts, width, height)
    fitted_bones = _fit_bones(edges, fitted_joints)

    shaded = _render_shaded_source(width, height, parts)
    overlay = _render_fit_overlay(width, height, parts, fitted_joints, fitted_bones)
    contact_sheet = _render_contact_sheet([("shaded source", shaded), ("skeleton fit", overlay)], scale)

    paths = {
        "overlay": output / "skeleton_fit_overlay.png",
        "contact_sheet": output / "skeleton_fit_contact_sheet.png",
    }
    _save_scaled(overlay, paths["overlay"], scale)
    contact_sheet.save(paths["contact_sheet"])

    report = {
        "schema": "glyph_lab.skeleton_fit.v0",
        "source_mannequin": str(recipe_path),
        "grid": {"width": width, "height": height},
        "joint_count": len(fitted_joints),
        "bone_count": len(fitted_bones),
        "joints": fitted_joints,
        "bones": fitted_bones,
        "confidence": _average_confidence(fitted_joints),
        "outputs": {key: str(path) for key, path in paths.items()},
        "rule": "anatomical skeleton landmarks are measured against body-part masks; part pivots remain attachment ownership points",
    }
    report_path = output / "skeleton_fit.json"
    _write_json(report_path, report)
    report["outputs"]["report"] = str(report_path)
    return report


def _load_parts(parts: list[dict[str, Any]], root: Path, width: int, height: int) -> dict[str, dict[str, Any]]:
    loaded = {}
    for part in parts:
        name = part.get("name")
        mask_path = _resolve_path(root, part.get("mask"))
        if not name or mask_path is None or not mask_path.exists():
            continue
        mask = _load_mask(mask_path, width, height)
        cutout_path = _resolve_path(root, part.get("cutout"))
        cutout = _load_cutout(cutout_path, width, height, mask) if cutout_path is not None and cutout_path.exists() else None
        loaded[name] = {**part, "_mask": mask, "_cutout": cutout}
    return loaded


def _fit_joints(
    joints: dict[str, list[int]],
    parts: dict[str, dict[str, Any]],
    width: int,
    height: int,
) -> dict[str, dict[str, Any]]:
    fitted = {}
    for name, point in joints.items():
        x, y = _point(point)
        source_parts = JOINT_SOURCE_PARTS.get(name, [])
        inside_expected = any(_mask_contains(parts.get(part_name), x, y) for part_name in source_parts)
        inside_any = any(_mask_contains(part, x, y) for part in parts.values())
        nearest = _nearest_bbox_distance(parts, source_parts, x, y)
        confidence = _joint_confidence(inside_expected, inside_any, nearest, width, height)
        fitted[name] = {
            "name": name,
            "point": [x, y],
            "source_parts_used": source_parts,
            "inside_expected_mask": inside_expected,
            "inside_any_body_mask": inside_any,
            "nearest_expected_bbox_distance": round(nearest, 2) if nearest is not None else None,
            "confidence": confidence,
        }
    return fitted


def _fit_bones(edges: list[list[str]], joints: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    bones = []
    for index, edge in enumerate(edges):
        if len(edge) != 2:
            continue
        a, b = edge
        if a not in joints or b not in joints:
            continue
        ax, ay = joints[a]["point"]
        bx, by = joints[b]["point"]
        length = math.hypot(bx - ax, by - ay)
        angle = math.degrees(math.atan2(by - ay, bx - ax))
        bones.append(
            {
                "id": f"bone.{index:02d}.{a}_to_{b}",
                "from": a,
                "to": b,
                "length": round(length, 2),
                "angle_degrees": round(angle, 2),
                "confidence": round((joints[a]["confidence"] + joints[b]["confidence"]) / 2, 3),
            }
        )
    return bones


def _joint_confidence(
    inside_expected: bool,
    inside_any: bool,
    nearest: float | None,
    width: int,
    height: int,
) -> float:
    if inside_expected:
        return 1.0
    if inside_any:
        return 0.78
    if nearest is None:
        return 0.0
    tolerance = max(6.0, min(width, height) * 0.025)
    if nearest <= tolerance:
        return 0.58
    falloff = max(1.0, min(width, height) * 0.16)
    return round(max(0.05, 0.58 - ((nearest - tolerance) / falloff)), 3)


def _nearest_bbox_distance(
    parts: dict[str, dict[str, Any]],
    source_parts: list[str],
    x: int,
    y: int,
) -> float | None:
    distances = []
    for name in source_parts:
        part = parts.get(name)
        if part and part.get("bbox"):
            distances.append(_distance_to_bbox(x, y, part["bbox"]))
    return min(distances) if distances else None


def _distance_to_bbox(x: int, y: int, bbox: list[int]) -> float:
    x0, y0, x1, y1 = [int(value) for value in bbox]
    dx = max(x0 - x, 0, x - x1)
    dy = max(y0 - y, 0, y - y1)
    return math.hypot(dx, dy)


def _mask_contains(part: dict[str, Any] | None, x: int, y: int) -> bool:
    if part is None:
        return False
    mask = part.get("_mask")
    if mask is None or x < 0 or y < 0 or x >= mask.width or y >= mask.height:
        return False
    return bool(mask.getpixel((x, y)))


def _render_shaded_source(width: int, height: int, parts: dict[str, dict[str, Any]]) -> Image.Image:
    image = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    ordered = sorted(parts.values(), key=lambda part: int(part.get("draw_order", 0)))
    for part in ordered:
        cutout = part.get("_cutout")
        if cutout is not None:
            image.alpha_composite(cutout)
    return image


def _render_fit_overlay(
    width: int,
    height: int,
    parts: dict[str, dict[str, Any]],
    joints: dict[str, dict[str, Any]],
    bones: list[dict[str, Any]],
) -> Image.Image:
    image = _render_shaded_source(width, height, parts)
    draw = ImageDraw.Draw(image)
    line_width = max(1, round(min(width, height) / 85))
    for part in parts.values():
        if part.get("bbox"):
            draw.rectangle(tuple(part["bbox"]), outline=(80, 80, 80), width=1)
    for bone in bones:
        a = joints[bone["from"]]["point"]
        b = joints[bone["to"]]["point"]
        draw.line((tuple(a), tuple(b)), fill=(10, 10, 10), width=line_width)
    radius = max(2, round(min(width, height) / 120))
    for joint in joints.values():
        point = tuple(joint["point"])
        color = _confidence_color(float(joint["confidence"]))
        draw.ellipse((point[0] - radius, point[1] - radius, point[0] + radius, point[1] + radius), fill=color, outline=(255, 255, 255))
    return image


def _confidence_color(confidence: float) -> tuple[int, int, int]:
    if confidence >= 0.9:
        return (20, 160, 70)
    if confidence >= 0.55:
        return (230, 150, 20)
    return (210, 40, 40)


def _render_contact_sheet(items: list[tuple[str, Image.Image]], scale: int) -> Image.Image:
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
    return sheet


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


def _resolve_path(root: Path, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else root / path


def _point(values: Any) -> tuple[int, int]:
    x, y = values
    return int(round(x)), int(round(y))


def _average_confidence(joints: dict[str, dict[str, Any]]) -> float:
    if not joints:
        return 0.0
    return round(sum(float(joint["confidence"]) for joint in joints.values()) / len(joints), 3)


def _save_scaled(image: Image.Image, output_path: Path, scale: int) -> None:
    image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST).save(output_path)


def _load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
