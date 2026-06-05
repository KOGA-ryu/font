from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from .atlas import PALETTE
from .candidate_filter import _records_with_bitmasks, filter_candidates
from .linework_primitives import default_linework_specs, linework_metadata, linework_stamp
from .measure import measure_stamp
from .review_export import generate_review_contact_sheet
from .schema import CELL_SIZE, load_glyphs
from .transforms import stamp_to_bitmask


LINEWORK_ASCII_FALLBACKS = {
    "horizontal": "-",
    "vertical": "|",
    "diagonal_rise": "/",
    "diagonal_fall": "\\",
    "corner": "+",
    "cap": "'",
    "hatch": "x",
}

EDGE_ALIASES = {
    "─": "-",
    "│": "|",
    "/": "/",
    "\\": "\\",
}


def generate_linework_candidates() -> list[dict[str, Any]]:
    candidates = []
    for index, spec in enumerate(default_linework_specs(), start=3000):
        color = PALETTE[spec["palette_role"]]
        stamp = linework_stamp(spec, color=color)
        features = measure_stamp(stamp)
        features["bitmask"] = stamp_to_bitmask(stamp)
        metadata = linework_metadata(spec)
        candidates.append(
            {
                "id": f"4.stone.linework.{spec['kind']}.{spec['name']}_{index}",
                "token": "",
                "index": index,
                "role": spec["role"],
                "family": spec["family"],
                "layer": spec["layer"],
                "palette_role": spec["palette_role"],
                "cell_size": CELL_SIZE,
                "features": features,
                "constraints": {"allowed_layers": [spec["layer"]], "forbidden_regions": ["background"]},
                "generated": True,
                "source": "geometry",
                "primitive_family": "linework",
                "primitive_params": spec["params"],
                "linework_kind": spec["kind"],
                "angle_degrees": metadata["angle_degrees"],
                "connector_sides": metadata["connector_sides"],
                "thickness": metadata["thickness"],
                "variant": metadata["variant"],
                "ascii_fallback": _ascii_fallback(spec, metadata),
            }
        )
    return candidates


def write_linework_review(pack_dir: str | Path) -> dict[str, Any]:
    pack = Path(pack_dir)
    candidates = generate_linework_candidates()
    existing = load_glyphs(pack / "glyphs.json")
    existing_records = _records_with_bitmasks(existing, pack / "atlas.png")
    result = filter_candidates(candidates, existing_accepted=existing_records)

    _write_json(pack / "linework_candidates.json", {"linework_candidates": candidates})
    _write_json(pack / "linework_candidate_scores.json", {"candidate_scores": result["candidate_scores"]})
    _write_json(
        pack / "linework_accepted_candidates.json",
        {"accepted_candidates": result["accepted_candidates"], "groups": result["groups"]},
    )
    _write_json(pack / "linework_rejected_candidates.json", {"rejected_candidates": result["rejected_candidates"]})
    generate_review_contact_sheet(
        result["accepted_candidates"],
        result["rejected_candidates"],
        pack / "linework_review_contact_sheet.png",
    )
    bridge = ascii_bridge_payload(existing_records, result["accepted_candidates"])
    _write_json(pack / "ascii_glyph_mapping.json", bridge)
    (pack / "ascii_linework_palette.txt").write_text(bridge["linework_palette"] + "\n", encoding="utf-8")
    (pack / "ascii_shade_palette.txt").write_text(bridge["shade_palette"] + "\n", encoding="utf-8")
    return {**result, "ascii_bridge": bridge}


def ascii_bridge_payload(
    active_records: list[dict[str, Any]],
    accepted_linework: list[dict[str, Any]],
) -> dict[str, Any]:
    used_tokens = {record.get("token") for record in active_records if record.get("token")}
    bridge_chars = _bridge_chars(accepted_linework, used_tokens)
    line_records = [
        _with_bridge_char(record, bridge_chars)
        for record in active_records + accepted_linework
        if record.get("layer") == "edge" or record.get("family") in {"linework", "corner", "junction", "diagonal"}
    ]
    shade_records = [
        _with_bridge_char(record, bridge_chars)
        for record in active_records
        if record.get("role") in {"void", "fill", "shadow", "highlight", "detail"}
        or record.get("layer") in {"base_fill", "shadow", "detail"}
    ]
    line_palette = _unique("".join(_palette_char(record) for record in line_records))
    shade_palette = _shade_palette(shade_records)
    mapping = {}
    for record in line_records + shade_records:
        token = _palette_char(record)
        mapping[token] = {
            "glyph_id": record["id"],
            "token": record.get("token", ""),
            "role": record.get("role"),
            "family": record.get("family"),
            "layer": record.get("layer"),
            "palette_role": record.get("palette_role"),
            "source": record.get("source", "active_pack"),
            "ascii_fallback": record.get("ascii_fallback", token),
            "bridge_only": not bool(record.get("token")),
        }
    _add_edge_aliases(mapping)
    return {
        "linework_palette": line_palette,
        "shade_palette": shade_palette,
        "mapping": mapping,
        "edge_aliases": EDGE_ALIASES,
        "notes": [
            "ASCII characters are bridge keys; glyph_lab tokens/stamps provide the rendered mark.",
            "Use --palette custom with these palette strings in image_to_ascii_workbench_v3.",
        ],
    }


def _ascii_fallback(spec: dict[str, Any], metadata: dict[str, Any]) -> str:
    if spec["kind"] == "line":
        params = spec["params"]
        return LINEWORK_ASCII_FALLBACKS[params["direction"]]
    if spec["kind"] == "corner":
        return LINEWORK_ASCII_FALLBACKS["corner"]
    if spec["kind"] == "hatch":
        return "/" if spec["params"]["kind"] == "diagonal_rise" else "\\" if spec["params"]["kind"] == "diagonal_fall" else "x"
    if spec["kind"] == "cap":
        return "-" if spec["params"]["direction"] == "horizontal" else "|"
    return metadata.get("variant", "?")[:1]


def _palette_char(record: dict[str, Any]) -> str:
    bridge_char = record.get("ascii_bridge_token")
    if bridge_char:
        return bridge_char
    token = record.get("token")
    if token:
        return token
    fallback = record.get("ascii_fallback")
    if fallback:
        return fallback
    return "?"


def _bridge_chars(records: list[dict[str, Any]], used_tokens: set[str]) -> dict[str, str]:
    preferred = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    punctuation = "!$%&'()+,-./:;<=>?@[]^_`{}~"
    pool = [char for char in preferred + punctuation if char not in used_tokens and char != " "]
    assigned: dict[str, str] = {}
    pool_index = 0
    for record in records:
        if record.get("token"):
            continue
        if pool_index >= len(pool):
            raise ValueError("not enough ASCII bridge characters for linework candidates")
        assigned[record["id"]] = pool[pool_index]
        pool_index += 1
    return assigned


def _with_bridge_char(record: dict[str, Any], bridge_chars: dict[str, str]) -> dict[str, Any]:
    if record.get("id") not in bridge_chars:
        return record
    copy = dict(record)
    copy["ascii_bridge_token"] = bridge_chars[record["id"]]
    return copy


def _shade_palette(records: list[dict[str, Any]]) -> str:
    sorted_records = sorted(records, key=lambda record: float(record.get("features", {}).get("density", 0.0)))
    return _unique("".join(_palette_char(record) for record in sorted_records))


def _unique(chars: str) -> str:
    seen = set()
    result = []
    for char in chars:
        if char not in seen and char != "":
            seen.add(char)
            result.append(char)
    return "".join(result)


def _add_edge_aliases(mapping: dict[str, dict[str, Any]]) -> None:
    for alias, canonical in EDGE_ALIASES.items():
        if alias in mapping or canonical not in mapping:
            continue
        entry = dict(mapping[canonical])
        entry["alias_for"] = canonical
        entry["bridge_only"] = True
        mapping[alias] = entry


def _write_json(path: str | Path, payload: dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
