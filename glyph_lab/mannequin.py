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

SKELETON_EDGE_ORDER = (
    ("neck", "chest"),
    ("chest", "pelvis"),
    ("chest", "shoulder_left"),
    ("shoulder_left", "elbow_left"),
    ("elbow_left", "wrist_left"),
    ("chest", "shoulder_right"),
    ("shoulder_right", "elbow_right"),
    ("elbow_right", "wrist_right"),
    ("pelvis", "hip_left"),
    ("hip_left", "knee_left"),
    ("knee_left", "ankle_left"),
    ("pelvis", "hip_right"),
    ("hip_right", "knee_right"),
    ("knee_right", "ankle_right"),
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
            "edges": _build_skeleton_edges(joints),
            "joint_rule": "joint estimates are anatomical centers from neighboring body-part bboxes; pivots remain body-part ownership points",
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

    def bbox(name: str) -> list[int] | None:
        part = by_name.get(name)
        return part["bbox"] if part is not None else None

    joints = {}
    mapping = {
        "neck": _joint_between(bbox("head"), bbox("neck"), "vertical") or _bbox_point(bbox("head"), 0.5, 1.0),
        "chest": _bbox_point(bbox("torso"), 0.5, 0.28),
        "pelvis": _bbox_point(bbox("pelvis"), 0.5, 0.45),
        "shoulder_left": _bbox_point(bbox("upper_arm_left"), 0.5, 0.10),
        "elbow_left": _joint_between(bbox("upper_arm_left"), bbox("lower_arm_left"), "vertical"),
        "wrist_left": _joint_between(bbox("lower_arm_left"), bbox("hand_left"), "vertical"),
        "hand_left": _bbox_point(bbox("hand_left"), 0.5, 0.5),
        "shoulder_right": _bbox_point(bbox("upper_arm_right"), 0.5, 0.10),
        "elbow_right": _joint_between(bbox("upper_arm_right"), bbox("lower_arm_right"), "vertical"),
        "wrist_right": _joint_between(bbox("lower_arm_right"), bbox("hand_right"), "vertical"),
        "hand_right": _bbox_point(bbox("hand_right"), 0.5, 0.5),
        "hip_left": _bbox_point(bbox("upper_leg_left"), 0.5, 0.08),
        "knee_left": _joint_between(bbox("upper_leg_left"), bbox("lower_leg_left"), "vertical"),
        "ankle_left": _joint_between(bbox("lower_leg_left"), bbox("foot_left"), "vertical"),
        "foot_left": _bbox_point(bbox("foot_left"), 0.55, 0.75),
        "hip_right": _bbox_point(bbox("upper_leg_right"), 0.5, 0.08),
        "knee_right": _joint_between(bbox("upper_leg_right"), bbox("lower_leg_right"), "vertical"),
        "ankle_right": _joint_between(bbox("lower_leg_right"), bbox("foot_right"), "vertical"),
        "foot_right": _bbox_point(bbox("foot_right"), 0.45, 0.75),
    }
    for name, point in mapping.items():
        if point is not None:
            joints[name] = point
    return joints


def _build_skeleton_edges(joints: dict[str, list[int]]) -> list[list[str]]:
    return [[a, b] for a, b in SKELETON_EDGE_ORDER if a in joints and b in joints]


def _bbox_point(bbox: list[int] | None, x_fraction: float, y_fraction: float) -> list[int] | None:
    if bbox is None:
        return None
    x0, y0, x1, y1 = bbox
    return [
        round(x0 + (x1 - x0) * x_fraction),
        round(y0 + (y1 - y0) * y_fraction),
    ]


def _joint_between(a: list[int] | None, b: list[int] | None, orientation: str) -> list[int] | None:
    if a is None or b is None:
        return None
    if orientation != "vertical":
        raise ValueError(f"unknown joint orientation {orientation!r}")
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return [
        round((((ax0 + ax1) / 2) + ((bx0 + bx1) / 2)) / 2),
        round((ay1 + by0) / 2),
    ]


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
