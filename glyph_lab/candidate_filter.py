from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from PIL import Image

from .atlas import load_atlas_stamps
from .equivalence import canonical_bitmask
from .schema import Glyph, load_glyphs
from .scoring import score_glyph
from .transforms import bitmask_to_stamp, stamp_to_bitmask


def filter_candidates(
    candidates: list[dict[str, Any] | Glyph],
    existing_accepted: list[dict[str, Any] | Glyph] | None = None,
) -> dict[str, Any]:
    selected: dict[tuple[str, int], str] = {}
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for existing in existing_accepted or []:
        record = _as_record(existing)
        canonical_id = _canonical_id(record)
        selected[(_equivalence_group(record), canonical_id)] = record.get("id", "existing")

    for candidate in candidates:
        scored = score_glyph(candidate)
        canonical_id = _canonical_id(scored)
        group = _equivalence_group(scored)
        scored["equivalence_group"] = group
        scored["canonical_id"] = canonical_id

        duplicate_key = (group, canonical_id)
        if scored["rejection_reason"] is None and duplicate_key in selected:
            scored["rejection_reason"] = "duplicate-canonical-id"
            scored["duplicate_of"] = selected[duplicate_key]
            scored["review_tags"] = list(scored["review_tags"]) + ["duplicate", "rejected"]
            scored["usefulness_score"] = min(scored["usefulness_score"], 0.25)

        if scored["rejection_reason"] is None and _too_similar(scored, accepted):
            scored["rejection_reason"] = "too-similar-to-existing-accepted-glyph"
            scored["review_tags"] = list(scored["review_tags"]) + ["similar", "rejected"]
            scored["usefulness_score"] = min(scored["usefulness_score"], 0.3)

        if scored["rejection_reason"] is None:
            selected[duplicate_key] = scored["id"]
            accepted.append(scored)
        else:
            rejected.append(scored)

    all_scores = accepted + rejected
    return {
        "candidate_scores": all_scores,
        "accepted_candidates": accepted,
        "rejected_candidates": rejected,
        "groups": _groups(accepted),
    }


def write_candidate_review(pack_dir: str | Path) -> dict[str, Any]:
    pack = Path(pack_dir)
    existing = load_glyphs(pack / "glyphs.json")
    generated = _load_generated_variants(pack / "generated_variants.json")
    existing_records = _records_with_bitmasks(existing, pack / "atlas.png")
    result = filter_candidates(generated, existing_accepted=existing_records)

    _write_json(pack / "candidate_scores.json", {"candidate_scores": result["candidate_scores"]})
    _write_json(
        pack / "accepted_candidates.json",
        {"accepted_candidates": result["accepted_candidates"], "groups": _groups(result["accepted_candidates"])},
    )
    _write_json(
        pack / "rejected_candidates.json",
        {"rejected_candidates": result["rejected_candidates"], "groups": _groups(result["rejected_candidates"])},
    )
    return result


def candidate_stamp(record: dict[str, Any]) -> Image.Image:
    bitmask = record.get("features", {}).get("bitmask")
    if bitmask is None:
        bitmask = record.get("canonical_id", 0)
    return bitmask_to_stamp(int(bitmask))


def _load_generated_variants(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data.get("generated_variants", data)


def _records_with_bitmasks(glyphs: list[Glyph], atlas_path: str | Path) -> list[dict[str, Any]]:
    stamps = load_atlas_stamps(atlas_path, glyphs)
    records = []
    for glyph in glyphs:
        record = glyph.to_dict()
        record["features"] = dict(record.get("features", {}))
        record["features"]["bitmask"] = stamp_to_bitmask(stamps[glyph.token])
        records.append(record)
    return records


def _canonical_id(record: dict[str, Any]) -> int:
    bitmask = record.get("features", {}).get("bitmask")
    if bitmask is None:
        return 0
    group = _equivalence_group(record)
    return canonical_bitmask(bitmask_to_stamp(int(bitmask)), group)[0]


def _equivalence_group(record: dict[str, Any]) -> str:
    role = record.get("role", "")
    family = record.get("family", "")
    if family in {"texture", "damage"}:
        return "translations_normalized"
    if family in {"corner", "junction"}:
        return "dihedral8"
    if family == "diagonal":
        return "mirrors"
    if role == "edge":
        return "rotations"
    return "exact"


def _too_similar(candidate: dict[str, Any], accepted: list[dict[str, Any]]) -> bool:
    bitmask = int(candidate.get("features", {}).get("bitmask", 0))
    for record in accepted:
        other = int(record.get("features", {}).get("bitmask", 0))
        if bitmask and bitmask == other:
            return True
    return False


def _groups(records: list[dict[str, Any]]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for record in records:
        key = f"{record.get('role', 'unknown')}/{record.get('family', 'unknown')}"
        grouped.setdefault(key, []).append(record["id"])
    return grouped


def _write_json(path: str | Path, payload: dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def _as_record(glyph: dict[str, Any] | Glyph) -> dict[str, Any]:
    return glyph if isinstance(glyph, dict) else glyph.to_dict()
