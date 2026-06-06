from __future__ import annotations

from pathlib import Path
from typing import Any
import json


BODY_PARTS = (
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
)

PARENT_BY_PART = {
    "head": "neck",
    "neck": "torso",
    "torso": "pelvis",
    "pelvis": None,
    "upper_arm_left": "torso",
    "lower_arm_left": "upper_arm_left",
    "hand_left": "lower_arm_left",
    "upper_arm_right": "torso",
    "lower_arm_right": "upper_arm_right",
    "hand_right": "lower_arm_right",
    "upper_leg_left": "pelvis",
    "lower_leg_left": "upper_leg_left",
    "foot_left": "lower_leg_left",
    "upper_leg_right": "pelvis",
    "lower_leg_right": "upper_leg_right",
    "foot_right": "lower_leg_right",
}

DRAW_ORDER = (
    "upper_arm_left",
    "lower_arm_left",
    "hand_left",
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
    "upper_arm_right",
    "lower_arm_right",
    "hand_right",
)


def build_mannequin_recipe(
    humanoid_regions_path: str | Path,
    output_path: str | Path,
    *,
    pose: str = "reference_pose",
) -> dict[str, Any]:
    regions_file = Path(humanoid_regions_path)
    regions = _load_json(regions_file)
    layers = {layer["lane"]: layer for layer in regions.get("layers", [])}
    width = int(regions.get("width", 0))
    height = int(regions.get("height", 0))
    if width <= 0 or height <= 0:
        raise ValueError("humanoid region manifest must include positive width and height")

    parts = []
    for name in BODY_PARTS:
        layer = layers.get(name)
        if layer is None or not layer.get("bbox"):
            continue
        bbox = [int(value) for value in layer["bbox"]]
        parts.append(
            {
                "name": name,
                "parent": PARENT_BY_PART[name],
                "draw_order": DRAW_ORDER.index(name),
                "mask": _relative_to_output(regions_file.parent, layer["mask"]),
                "cutout": _relative_to_output(regions_file.parent, layer["cutout"]),
                "cropped_cutout": _relative_to_output(regions_file.parent, layer.get("cropped_cutout")),
                "bbox": bbox,
                "pivot": _pivot_for_part(name, bbox),
                "socket": f"{name}_socket",
                "pixel_count": int(layer.get("pixels", 0)),
            }
        )

    joints = _build_joints(parts)
    recipe = {
        "schema": "glyph_lab.mannequin.v0",
        "source_regions": str(regions_file),
        "source_image": regions.get("source_image"),
        "pose": pose,
        "grid": {"width": width, "height": height},
        "origin": "bottom_center",
        "rule": "mannequin is pose and body structure only; color, hair, clothing, cape, props, and texture are attachment/render lanes",
        "parts": parts,
        "skeleton": {
            "root": "pelvis",
            "parents": {part["name"]: part["parent"] for part in parts},
            "joints": joints,
        },
        "draw_order": [part["name"] for part in sorted(parts, key=lambda item: item["draw_order"])],
        "sockets": _build_sockets(parts, joints),
    }
    output_file = _output_file(output_path, "mannequin_recipe.json")
    _write_json(output_file, recipe)
    return recipe


def _pivot_for_part(name: str, bbox: list[int]) -> list[int]:
    x0, y0, x1, y1 = bbox
    cx = round((x0 + x1) / 2)
    cy = round((y0 + y1) / 2)
    if name == "head":
        return [cx, y1]
    if name == "neck":
        return [cx, y0]
    if name == "torso":
        return [cx, y0]
    if name == "pelvis":
        return [cx, y0]
    if name.startswith("upper_arm"):
        return [x1 if name.endswith("left") else x0, y0]
    if name.startswith("lower_arm"):
        return [x1 if name.endswith("left") else x0, y0]
    if name.startswith("hand"):
        return [cx, y0]
    if name.startswith("upper_leg"):
        return [cx, y0]
    if name.startswith("lower_leg"):
        return [cx, y0]
    if name.startswith("foot"):
        return [cx, y0]
    return [cx, cy]


def _build_joints(parts: list[dict[str, Any]]) -> dict[str, list[int]]:
    by_name = {part["name"]: part for part in parts}

    def pivot(name: str) -> list[int] | None:
        part = by_name.get(name)
        return part["pivot"] if part is not None else None

    joints = {}
    mapping = {
        "neck": pivot("head") or pivot("neck"),
        "chest": pivot("torso"),
        "pelvis": pivot("pelvis"),
        "shoulder_left": pivot("upper_arm_left"),
        "elbow_left": pivot("lower_arm_left"),
        "hand_left": pivot("hand_left"),
        "shoulder_right": pivot("upper_arm_right"),
        "elbow_right": pivot("lower_arm_right"),
        "hand_right": pivot("hand_right"),
        "hip_left": pivot("upper_leg_left"),
        "knee_left": pivot("lower_leg_left"),
        "foot_left": pivot("foot_left"),
        "hip_right": pivot("upper_leg_right"),
        "knee_right": pivot("lower_leg_right"),
        "foot_right": pivot("foot_right"),
    }
    for name, point in mapping.items():
        if point is not None:
            joints[name] = point
    return joints


def _build_sockets(parts: list[dict[str, Any]], joints: dict[str, list[int]]) -> list[dict[str, Any]]:
    sockets = []
    for part in parts:
        sockets.append(
            {
                "name": f"{part['name']}_socket",
                "part": part["name"],
                "point": part["pivot"],
                "purpose": "body_part_attachment",
            }
        )
    for name, point in joints.items():
        sockets.append({"name": f"{name}_joint", "part": name, "point": point, "purpose": "pose_joint"})
    return sockets


def _relative_to_output(root: Path, value: str | None) -> str | None:
    if not value:
        return None
    path = Path(value)
    return str(path if path.is_absolute() else root / path)


def _output_file(output_path: str | Path, default_name: str) -> Path:
    path = Path(output_path)
    return path if path.suffix.lower() == ".json" else path / default_name


def _load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: str | Path, payload: dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
