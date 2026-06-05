from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from .atlas import PALETTE
from .brush_primitives import brush_metadata, brush_stamp, default_brush_specs
from .candidate_filter import _records_with_bitmasks, filter_candidates
from .measure import measure_stamp
from .review_export import generate_review_contact_sheet
from .schema import CELL_SIZE, load_glyphs
from .transforms import stamp_to_bitmask


def generate_brush_candidates() -> list[dict[str, Any]]:
    candidates = []
    for index, spec in enumerate(default_brush_specs(), start=4000):
        metadata = brush_metadata(spec)
        stamp = brush_stamp(spec["brush_family"], color=PALETTE[spec["palette_role"]], **spec["params"])
        features = measure_stamp(stamp)
        features["bitmask"] = stamp_to_bitmask(stamp)
        candidates.append(
            {
                "id": f"4.stone.brush.{spec['brush_family']}.{spec['name']}_{index}",
                "token": "",
                "index": index,
                "role": spec["role"],
                "family": spec["family"],
                "layer": spec["layer"],
                "palette_role": spec["palette_role"],
                "cell_size": CELL_SIZE,
                "features": features,
                "constraints": {"allowed_layers": [spec["layer"]], "allowed_regions": ["surface", "shadow", "detail"]},
                "generated": True,
                "source": "brush_geometry",
                "primitive_family": "brush",
                "primitive_params": spec["params"],
                **metadata,
            }
        )
    return candidates


def write_brush_review(pack_dir: str | Path) -> dict[str, Any]:
    pack = Path(pack_dir)
    candidates = generate_brush_candidates()
    existing = load_glyphs(pack / "glyphs.json")
    existing_records = _records_with_bitmasks(existing, pack / "atlas.png")
    result = filter_candidates(candidates, existing_accepted=existing_records)

    _write_json(pack / "brush_candidates.json", {"brush_candidates": candidates})
    _write_json(pack / "brush_candidate_scores.json", {"candidate_scores": result["candidate_scores"]})
    _write_json(
        pack / "brush_accepted_candidates.json",
        {"accepted_candidates": result["accepted_candidates"], "groups": result["groups"]},
    )
    _write_json(pack / "brush_rejected_candidates.json", {"rejected_candidates": result["rejected_candidates"]})
    generate_review_contact_sheet(
        result["accepted_candidates"],
        result["rejected_candidates"],
        pack / "brush_review_contact_sheet.png",
    )

    bridge = brush_ascii_bridge_payload(existing_records, result["accepted_candidates"])
    _write_json(pack / "ascii_brush_mapping.json", bridge)
    (pack / "ascii_texture_palette.txt").write_text(bridge["texture_palette"] + "\n", encoding="utf-8")
    (pack / "ascii_spray_palette.txt").write_text(bridge["spray_palette"] + "\n", encoding="utf-8")
    return {**result, "ascii_bridge": bridge}


def brush_ascii_bridge_payload(
    active_records: list[dict[str, Any]],
    accepted_brushes: list[dict[str, Any]],
) -> dict[str, Any]:
    used_tokens = {record.get("token") for record in active_records if record.get("token")}
    bridge_chars = _bridge_chars(accepted_brushes, used_tokens)
    active_texture = [
        record
        for record in active_records
        if record.get("family") in {"texture", "damage"} or record.get("role") in {"detail", "fill", "shadow"}
    ]
    brush_records = [_with_bridge_char(record, bridge_chars) for record in accepted_brushes]
    all_records = active_texture + brush_records
    texture_records = [
        record
        for record in all_records
        if record.get("family") in {"texture", "charcoal", "dry_brush", "grain", "damage"}
        or record.get("brush_family") in {"hatch", "crosshatch", "charcoal", "dry_brush", "grain"}
    ]
    spray_records = [
        record
        for record in all_records
        if record.get("family") == "spray" or record.get("brush_family") in {"stipple", "spray"}
    ]
    mapping = {}
    for record in all_records:
        token = _palette_char(record)
        mapping[token] = {
            "glyph_id": record["id"],
            "token": record.get("token", ""),
            "role": record.get("role"),
            "family": record.get("family"),
            "layer": record.get("layer"),
            "palette_role": record.get("palette_role"),
            "source": record.get("source", "active_pack"),
            "brush_family": record.get("brush_family"),
            "brush_engine": record.get("brush_engine"),
            "density_class": record.get("density_class"),
            "ascii_fallback": record.get("ascii_fallback", token),
            "bridge_only": not bool(record.get("token")),
        }
    return {
        "texture_palette": _density_palette(texture_records),
        "spray_palette": _density_palette(spray_records),
        "mapping": mapping,
        "notes": [
            "Brush palettes model digital brush concepts as 4x4 glyph stamps.",
            "Texture palettes cover hatch, crosshatch, charcoal, dry brush, and grain.",
            "Spray palettes cover stipple and scatter-style glyphs.",
        ],
    }


def _bridge_chars(records: list[dict[str, Any]], used_tokens: set[str]) -> dict[str, str]:
    preferred = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    punctuation = "!$%&'()+,-./:;<=>?@[]^_`{}~"
    pool = [char for char in preferred + punctuation if char not in used_tokens and char != " "]
    assigned: dict[str, str] = {}
    for record, char in zip([record for record in records if not record.get("token")], pool):
        assigned[record["id"]] = char
    if len(assigned) < sum(1 for record in records if not record.get("token")):
        raise ValueError("not enough ASCII bridge characters for brush candidates")
    return assigned


def _with_bridge_char(record: dict[str, Any], bridge_chars: dict[str, str]) -> dict[str, Any]:
    if record.get("id") not in bridge_chars:
        return record
    copy = dict(record)
    copy["ascii_bridge_token"] = bridge_chars[record["id"]]
    return copy


def _density_palette(records: list[dict[str, Any]]) -> str:
    return _unique(
        "".join(
            _palette_char(record)
            for record in sorted(records, key=lambda item: float(item.get("features", {}).get("density", 0.0)))
        )
    )


def _palette_char(record: dict[str, Any]) -> str:
    return record.get("ascii_bridge_token") or record.get("token") or record.get("ascii_fallback") or "?"


def _unique(chars: str) -> str:
    seen = set()
    result = []
    for char in chars:
        if char not in seen and char != "":
            seen.add(char)
            result.append(char)
    return "".join(result)


def _write_json(path: str | Path, payload: dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
