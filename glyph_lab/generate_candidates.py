from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from .atlas import PALETTE
from .candidate_filter import _records_with_bitmasks, filter_candidates
from .measure import measure_stamp
from .primitives import primitive_stamp
from .review_export import generate_review_contact_sheet
from .schema import CELL_SIZE, load_glyphs
from .transforms import stamp_to_bitmask


def generate_primitive_candidates() -> list[dict[str, Any]]:
    specs = _primitive_specs()
    candidates = []
    for index, spec in enumerate(specs, start=2000):
        stamp = primitive_stamp(spec["primitive_family"], **spec["primitive_params"], color=PALETTE[spec["palette_role"]])
        features = measure_stamp(stamp)
        features["bitmask"] = stamp_to_bitmask(stamp)
        candidates.append(
            {
                "id": f"4.stone.primitive.{spec['primitive_family']}.{spec['name']}_{index}",
                "token": spec.get("token", ""),
                "index": index,
                "role": spec["role"],
                "family": spec["family"],
                "layer": spec["layer"],
                "palette_role": spec["palette_role"],
                "cell_size": CELL_SIZE,
                "features": features,
                "constraints": {},
                "generated": True,
                "source": "primitive",
                "primitive_family": spec["primitive_family"],
                "primitive_params": spec["primitive_params"],
            }
        )
    return candidates


def write_primitive_review(pack_dir: str | Path) -> dict[str, Any]:
    pack = Path(pack_dir)
    candidates = generate_primitive_candidates()
    existing = load_glyphs(pack / "glyphs.json")
    existing_records = _records_with_bitmasks(existing, pack / "atlas.png")
    result = filter_candidates(candidates, existing_accepted=existing_records)

    _write_json(pack / "primitive_candidates.json", {"primitive_candidates": candidates})
    _write_json(pack / "primitive_candidate_scores.json", {"candidate_scores": result["candidate_scores"]})
    _write_json(
        pack / "primitive_accepted_candidates.json",
        {"accepted_candidates": result["accepted_candidates"], "groups": result["groups"]},
    )
    _write_json(
        pack / "primitive_rejected_candidates.json",
        {"rejected_candidates": result["rejected_candidates"]},
    )
    generate_review_contact_sheet(
        result["accepted_candidates"],
        result["rejected_candidates"],
        pack / "primitive_review_contact_sheet.png",
    )
    return result


def _primitive_specs() -> list[dict[str, Any]]:
    return [
        _spec("point", "dot_1_2", {"x": 1, "y": 2}, "detail", "damage", "detail", "crack"),
        _spec("point", "bad_edge_dot", {"x": 1, "y": 1}, "edge", "vertical", "edge", "ink"),
        _spec("line", "horizontal_thin", {"orientation": "horizontal", "thickness": 1}, "edge", "horizontal", "edge", "ink"),
        _spec("line", "vertical_thin", {"orientation": "vertical", "thickness": 1}, "edge", "vertical", "edge", "ink"),
        _spec("line", "horizontal_broken", {"orientation": "horizontal", "thickness": 1, "broken": True}, "edge", "horizontal", "edge", "ink"),
        _spec("line", "diagonal_rise_thin", {"orientation": "diagonal_rise", "thickness": 1}, "edge", "diagonal", "edge", "ink"),
        _spec("line", "diagonal_fall_thin", {"orientation": "diagonal_fall", "thickness": 1}, "edge", "diagonal", "edge", "ink"),
        _spec("block", "solid", {"kind": "solid"}, "mass", "solid", "base_fill", "stone_mid"),
        _spec("block", "three_quarter_no_top_left", {"kind": "three_quarter_no_top_left"}, "mass", "three_quarter", "base_fill", "stone_mid"),
        _spec("block", "three_quarter_no_bottom_right", {"kind": "three_quarter_no_bottom_right"}, "mass", "three_quarter", "base_fill", "stone_dark"),
        _spec("corner", "top_left_thick", {"position": "top_left", "thickness": 2}, "edge", "corner", "edge", "ink"),
        _spec("corner", "bottom_right_thick", {"position": "bottom_right", "thickness": 2}, "edge", "corner", "edge", "ink"),
        _spec("crack", "vertical_jagged", {"kind": "vertical_jagged"}, "detail", "damage", "detail", "crack"),
        _spec("crack", "forked", {"kind": "forked"}, "detail", "damage", "detail", "crack"),
        _spec("fill", "checker", {"kind": "checker"}, "fill", "texture", "base_fill", "stone_mid"),
        _spec("fill", "noise_seed_7", {"kind": "noise", "seed": 7}, "fill", "texture", "base_fill", "stone_light"),
        _spec("bevel", "highlight_top_left", {"kind": "highlight_top_left"}, "highlight", "bevel", "detail", "highlight"),
        _spec("bevel", "shadow_bottom_right", {"kind": "shadow_bottom_right"}, "shadow", "bevel", "shadow", "stone_dark"),
        _spec("bevel", "diagonal", {"kind": "diagonal"}, "highlight", "bevel", "detail", "highlight"),
    ]


def _spec(
    primitive_family: str,
    name: str,
    primitive_params: dict[str, Any],
    role: str,
    family: str,
    layer: str,
    palette_role: str,
) -> dict[str, Any]:
    return {
        "primitive_family": primitive_family,
        "name": name,
        "primitive_params": primitive_params,
        "role": role,
        "family": family,
        "layer": layer,
        "palette_role": palette_role,
    }


def _write_json(path: str | Path, payload: dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
