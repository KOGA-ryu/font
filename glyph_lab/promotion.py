from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
import re
import shutil

from PIL import Image

from .candidate_filter import _canonical_id, _equivalence_group
from .measure import measure_stamp
from .motion_taxonomy import MOTION_METADATA_FIELDS
from .schema import CELL_SIZE
from .token_allocator import allocate_token
from .transforms import bitmask_to_stamp, stamp_to_bitmask


PROMOTION_VERSION = "glyph_lab_v0"


def promote_candidates(
    pack_dir: str | Path,
    request_path: str | Path,
    apply: bool = False,
    accepted_path: str | Path | None = None,
    base_glyphs_path: str | Path | None = None,
) -> dict[str, Any]:
    pack = Path(pack_dir)
    accepted_source = Path(accepted_path) if accepted_path is not None else pack / "primitive_accepted_candidates.json"
    base_glyphs = Path(base_glyphs_path) if base_glyphs_path is not None else pack / "glyphs.json"
    request = _load_request(request_path)
    active_records = _load_records(base_glyphs)
    accepted = {
        candidate["id"]: candidate
        for candidate in _load_accepted(accepted_source)
    }
    active_canonicals = _active_canonical_keys(active_records, pack / "atlas.png")
    used_tokens = {record["token"] for record in active_records}
    next_index = max(int(record.get("index", -1)) for record in active_records) + 1

    promoted_records: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    token_assignments: dict[str, str] = {}

    for item in request.get("promote", []):
        candidate_id = item.get("candidate_id")
        if not candidate_id:
            rejected.append({"candidate_id": "", "reason": "missing-candidate-id"})
            continue
        candidate = accepted.get(candidate_id)
        if candidate is None:
            rejected.append({"candidate_id": candidate_id, "reason": "candidate-not-in-accepted-list"})
            continue

        token = item.get("token") or None
        if token is not None and (len(token) != 1 or token == " "):
            rejected.append({"candidate_id": candidate_id, "reason": "invalid-token"})
            continue
        if token is not None and token in used_tokens:
            rejected.append({"candidate_id": candidate_id, "reason": "token-already-exists"})
            continue

        canonical_key = (_equivalence_group(candidate), _canonical_id(candidate))
        if canonical_key in active_canonicals and not item.get("force_duplicate", False):
            rejected.append({"candidate_id": candidate_id, "reason": "duplicate-canonical-id"})
            continue

        if token is None:
            try:
                token = allocate_token(used_tokens)
            except ValueError as exc:
                rejected.append({"candidate_id": candidate_id, "reason": str(exc)})
                continue

        used_tokens.add(token)
        glyph_id = item.get("id") or _stable_glyph_id(candidate, next_index)
        promoted = _promoted_record(candidate, token, glyph_id, next_index, item.get("notes"), accepted_source.name)
        promoted_records.append(promoted)
        token_assignments[candidate_id] = token
        active_canonicals.add(canonical_key)
        next_index += 1

    output_records = active_records + promoted_records
    promoted_path = pack / "glyphs.promoted.json"
    _write_records(promoted_path, output_records)

    backup_path = None
    if apply:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = pack / f"glyphs.backup.{timestamp}.json"
        shutil.copy2(pack / "glyphs.json", backup_path)
        _write_records(pack / "glyphs.json", output_records)

    report = {
        "promoted_count": len(promoted_records),
        "rejected_count": len(rejected),
        "promoted_candidate_ids": [record["source_candidate_id"] for record in promoted_records],
        "rejected_candidate_ids": rejected,
        "token_assignments": token_assignments,
        "apply": apply,
        "backup_path": str(backup_path) if backup_path else None,
        "output_path": str(promoted_path),
        "accepted_source": str(accepted_source),
        "base_glyphs_path": str(base_glyphs),
    }
    _write_json(pack / "promotion_report.json", report)
    return report


def _promoted_record(
    candidate: dict[str, Any],
    token: str,
    glyph_id: str,
    index: int,
    notes: str | None,
    promoted_from: str,
) -> dict[str, Any]:
    bitmask = int(candidate.get("features", {}).get("bitmask", 0))
    stamp = bitmask_to_stamp(bitmask)
    features = measure_stamp(stamp)
    features["bitmask"] = stamp_to_bitmask(stamp)
    record = {
        "id": glyph_id,
        "token": token,
        "index": index,
        "role": candidate["role"],
        "family": candidate["family"],
        "layer": candidate["layer"],
        "palette_role": candidate["palette_role"],
        "cell_size": CELL_SIZE,
        "features": features,
        "constraints": candidate.get("constraints", {}),
        "generated": True,
        "source": candidate.get("source", "primitive"),
        "primitive_family": candidate.get("primitive_family"),
        "primitive_params": candidate.get("primitive_params", {}),
        "source_candidate_id": candidate["id"],
        "promoted_from": promoted_from,
        "promoted_at_version": PROMOTION_VERSION,
    }
    if notes is not None:
        record["notes"] = notes
    lineage_keys = (
        "linework_kind",
        "linework_package",
        "stroke_topology",
        "stroke_ports",
        "angle_degrees",
        "connector_sides",
        "thickness",
        "variant",
        "weight_profile",
        "cap_style",
        "join_style",
        "break_rhythm",
        "roughness",
        "continuity",
        "repeat_angle_degrees",
        "spacing_class",
        "intended_continuity",
        "visible_fragments",
        "dropout_ratio",
        "coverage",
        "branch_count",
        "dominant_angle_degrees",
        "entry_tangent_degrees",
        "exit_tangent_degrees",
        "curvature",
        "terminal_ports",
        "stroke_style",
        "ascii_fallback",
        "brush_family",
        "brush_params",
        "brush_engine",
        "density_class",
    ) + MOTION_METADATA_FIELDS
    for key in lineage_keys:
        if key in candidate:
            record[key] = candidate[key]
    return record


def _active_canonical_keys(records: list[dict[str, Any]], atlas_path: Path) -> set[tuple[str, int]]:
    records_with_bits = []
    atlas = Image.open(atlas_path).convert("RGBA") if atlas_path.exists() else None
    for record in records:
        record = deepcopy(record)
        if record.get("features", {}).get("bitmask") is None and atlas is not None:
            bitmask = _bitmask_from_atlas(atlas, record)
            if bitmask is not None:
                record.setdefault("features", {})["bitmask"] = bitmask
        if record.get("features", {}).get("bitmask") is not None:
            records_with_bits.append(record)
    return {(_equivalence_group(record), _canonical_id(record)) for record in records_with_bits}


def _bitmask_from_atlas(atlas: Image.Image, record: dict[str, Any]) -> int | None:
    cell_size = int(record.get("cell_size", CELL_SIZE))
    index = int(record.get("index", -1))
    if index < 0:
        return None
    x = (index % 8) * cell_size
    y = (index // 8) * cell_size
    if x + cell_size > atlas.width or y + cell_size > atlas.height:
        return None
    return stamp_to_bitmask(atlas.crop((x, y, x + cell_size, y + cell_size)))


def _load_request(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if "promote" not in data or not isinstance(data["promote"], list):
        raise ValueError("promotion request must contain a promote list")
    return data


def _load_accepted(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data.get("accepted_candidates", data)


def _load_records(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data.get("glyphs", data)


def _write_records(path: str | Path, records: list[dict[str, Any]]) -> None:
    _write_json(path, {"glyphs": records})


def _write_json(path: str | Path, payload: dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def _stable_glyph_id(candidate: dict[str, Any], index: int) -> str:
    suffix = candidate["id"].split(".")[-1]
    suffix = re.sub(r"[^A-Za-z0-9_]+", "_", suffix)
    return f"4.stone.promoted.{candidate['role']}.{candidate['family']}.{suffix}_{index:02d}"
