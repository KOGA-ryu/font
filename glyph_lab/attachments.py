from __future__ import annotations

from pathlib import Path
from typing import Any
import json


ATTACHMENT_RULES = {
    "hair": {
        "attach_to": "head_socket",
        "parent_part": "head",
        "draw_order": "front_of_head",
        "motion_behavior": "rigid_or_soft_follow",
        "allowed_pose_warp": {"rotate_degrees": 18, "stretch": 0.05, "bend": 0.1},
    },
    "clothing": {
        "attach_to": "torso_socket",
        "parent_part": "torso",
        "draw_order": "over_body",
        "motion_behavior": "body_follow",
        "allowed_pose_warp": {"rotate_degrees": 8, "stretch": 0.08, "bend": 0.08},
    },
    "leather": {
        "attach_to": "pelvis_socket",
        "parent_part": "pelvis",
        "draw_order": "over_body",
        "motion_behavior": "body_follow",
        "allowed_pose_warp": {"rotate_degrees": 8, "stretch": 0.08, "bend": 0.08},
    },
    "metal": {
        "attach_to": "hand_right_socket",
        "parent_part": "hand_right",
        "draw_order": "front",
        "motion_behavior": "rigid_follow",
        "allowed_pose_warp": {"rotate_degrees": 20, "stretch": 0.02, "bend": 0.0},
    },
    "gold": {
        "attach_to": "torso_socket",
        "parent_part": "torso",
        "draw_order": "front",
        "motion_behavior": "rigid_follow",
        "allowed_pose_warp": {"rotate_degrees": 10, "stretch": 0.02, "bend": 0.0},
    },
    "highlight": {
        "attach_to": "body_surface",
        "parent_part": "body",
        "draw_order": "front",
        "motion_behavior": "surface_follow",
        "allowed_pose_warp": {"rotate_degrees": 6, "stretch": 0.04, "bend": 0.04},
    },
}


def build_attachment_recipe(
    sprite_parts_path: str | Path,
    output_path: str | Path,
    *,
    mannequin_path: str | Path | None = None,
) -> dict[str, Any]:
    parts_file = Path(sprite_parts_path)
    parts_manifest = _load_json(parts_file)
    layers = [layer for layer in parts_manifest.get("layers", []) if int(layer.get("cells", 0)) > 0]
    attachments = []
    for layer in layers:
        part = layer.get("part")
        if part in {"outline", "skin"}:
            continue
        rule = ATTACHMENT_RULES.get(part, _default_rule(part))
        bbox = _layer_bbox(layer)
        attachments.append(
            {
                "name": part,
                "source_part": part,
                "attach_to": rule["attach_to"],
                "parent_part": rule["parent_part"],
                "draw_order": rule["draw_order"],
                "mask": _relative_to_output(parts_file.parent, layer.get("mask")),
                "colorized_layer": _relative_to_output(parts_file.parent, layer.get("colorized_layer")),
                "bbox": bbox,
                "anchor": _anchor_for_attachment(part, bbox),
                "cell_count": int(layer.get("cells", 0)),
                "average_hex": layer.get("average_hex"),
                "motion_behavior": rule["motion_behavior"],
                "allowed_pose_warp": rule["allowed_pose_warp"],
            }
        )

    recipe = {
        "schema": "glyph_lab.attachments.v0",
        "source_parts": str(parts_file),
        "source_image": parts_manifest.get("source_image"),
        "mannequin": str(mannequin_path) if mannequin_path is not None else None,
        "grid": {
            "width": int(parts_manifest.get("grid_width", 0)),
            "height": int(parts_manifest.get("grid_height", 0)),
        },
        "rule": "attachments are separate silhouettes anchored to mannequin sockets; final color and glyph texture remain render-lane concerns",
        "attachments": attachments,
    }
    output_file = _output_file(output_path, "attachment_recipe.json")
    _write_json(output_file, recipe)
    return recipe


def _layer_bbox(layer: dict[str, Any]) -> list[int] | None:
    components = layer.get("components") or []
    if not components:
        return None
    bboxes = [component["bbox"] for component in components if component.get("bbox")]
    if not bboxes:
        return None
    return [
        min(bbox[0] for bbox in bboxes),
        min(bbox[1] for bbox in bboxes),
        max(bbox[2] for bbox in bboxes),
        max(bbox[3] for bbox in bboxes),
    ]


def _anchor_for_attachment(part: str, bbox: list[int] | None) -> list[int] | None:
    if bbox is None:
        return None
    x0, y0, x1, y1 = bbox
    cx = round((x0 + x1) / 2)
    if part == "hair":
        return [cx, y1]
    if part in {"clothing", "gold", "highlight"}:
        return [cx, y0]
    if part == "leather":
        return [cx, y0]
    if part == "metal":
        return [x0, round((y0 + y1) / 2)]
    return [cx, y0]


def _default_rule(part: str | None) -> dict[str, Any]:
    return {
        "attach_to": "body_surface",
        "parent_part": "body",
        "draw_order": "front",
        "motion_behavior": f"{part or 'unknown'}_surface_follow",
        "allowed_pose_warp": {"rotate_degrees": 8, "stretch": 0.05, "bend": 0.05},
    }


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
